# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api
from psycopg2 import sql


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    filter_analytic_groupby = fields.Boolean(
        string="Filter Analytic Groupby",
        compute=lambda x: x._compute_report_option_filter('filter_analytic_groupby'), readonly=False, store=True, depends=['root_report_id'],
    )

    def _get_options_initializers_forced_sequence_map(self):
        """ Force the sequence for the init_options so columns groups are already generated """
        sequence_map = super(AccountReport, self)._get_options_initializers_forced_sequence_map()
        sequence_map[self._init_options_analytic_groupby] = 1050
        return sequence_map

    def _init_options_analytic_groupby(self, options, previous_options=None):
        if not self.filter_analytic_groupby:
            return
        enable_analytic_accounts = self.user_has_groups('analytic.group_analytic_accounting')
        if not enable_analytic_accounts:
            return

        options['analytic_groupby'] = True
        options['analytic_plan_groupby'] = True

        previous_analytic_accounts = (previous_options or {}).get('analytic_accounts_groupby', [])
        analytic_account_ids = [int(x) for x in previous_analytic_accounts]
        selected_analytic_accounts = self.env['account.analytic.account'].search(
            [('id', 'in', analytic_account_ids)])
        options['analytic_accounts_groupby'] = selected_analytic_accounts.ids
        options['selected_analytic_account_groupby_names'] = selected_analytic_accounts.mapped('name')

        previous_analytic_plans = (previous_options or {}).get('analytic_plans_groupby', [])
        analytic_plan_ids = [int(x) for x in previous_analytic_plans]
        selected_analytic_plans = self.env['account.analytic.plan'].search([('id', 'in', analytic_plan_ids)])
        options['analytic_plans_groupby'] = selected_analytic_plans.ids
        options['selected_analytic_plan_groupby_names'] = selected_analytic_plans.mapped('name')

        self._create_column_analytic(options)

    def _create_column_analytic(self, options):
        """ Creates the analytic columns for each plan or account in the filters.
        This will duplicate all previous columns and adding the analytic accounts in the domain of the added columns.

        The analytic_groupby_option is used so the table used is the shadowed table.
        The domain on analytic_distribution_stored_char can just use simple comparison as the column of the shadowed
        table will simply be filled with analytic_account_ids.
        """

        analytic_headers = []
        plans = self.env['account.analytic.plan'].browse(options.get('analytic_plans_groupby'))
        for plan in plans:
            account_list = []
            accounts = self.env['account.analytic.account'].search([('root_plan_id', '=', plan.id)])
            for account in accounts:
                account_list.append(str(account.id))
            analytic_headers.append({
                'name': plan.name,
                'forced_options': {'analytic_groupby_option': True,
                                   'forced_domain': [('analytic_distribution_stored_char', 'in', tuple(account_list))]}
            })

        accounts = self.env['account.analytic.account'].browse(options.get('analytic_accounts_groupby'))
        for account in accounts:
            analytic_headers.append({
                'name': account.name,
                'forced_options': {'analytic_groupby_option': True,
                                   'forced_domain': [('analytic_distribution_stored_char', 'ilike', str(account.id))]}
            })
        if analytic_headers:
            analytic_headers.append({'name': ''})
            default_group_vals = {'horizontal_groupby_element': {}, 'forced_options': {}}
            options['column_headers'] = [
                *options['column_headers'],
                analytic_headers,
            ]
            initial_column_group_vals = self._generate_columns_group_vals_recursively(options['column_headers'], default_group_vals)
            options['columns'], options['column_groups'] = self._build_columns_from_column_group_vals(options, initial_column_group_vals)

    @api.model
    def _prepare_lines_for_analytic_groupby(self):
        """Prepare the analytic_temp_account_move_line

        This method should be used once before all the SQL queries using the
        table account_move_line for the analytic columns for the financial reports.
        It will create a new table with the schema of account_move_line table, but with
        the data from account_analytic_line.

        We inherit the schema of account_move_line, make the correspondence between
        account_move_line fields and account_analytic_line fields and put NULL for those
        who don't exist in account_analytic_line.
        We also drop the NOT NULL constraints for fields who are not required in account_analytic_line.
        """
        self.env.cr.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name='analytic_temp_account_move_line'")
        if self.env.cr.fetchone():
            return

        line_fields = self.env['account.move.line'].fields_get()
        self.env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='account_move_line'")
        stored_fields = set(f[0] for f in self.env.cr.fetchall())
        changed_equivalence_dict = {
            "id": sql.Identifier("move_line_id"),
            "balance": sql.SQL("-amount"),
            "company_id": sql.Identifier("company_id"),
            "journal_id": sql.Identifier("journal_id"),
            "display_type": sql.Literal("product"),
            "parent_state": sql.Literal("posted"),
            "date": sql.Identifier("date"),
            "analytic_distribution_stored_char": sql.Identifier("account_id"),
            "account_id": sql.Identifier("general_account_id"),
            "partner_id": sql.Identifier("partner_id"),
            "debit": sql.SQL("CASE WHEN (amount < 0) THEN amount else 0 END"),
            "credit": sql.SQL("CASE WHEN (amount > 0) THEN amount else 0 END"),
        }
        selected_fields = []
        for fname in stored_fields:
            if fname in changed_equivalence_dict:
                selected_fields.append(sql.SQL('{original} AS "account_move_line.{asname}"').format(
                    original=changed_equivalence_dict[fname],
                    asname=sql.SQL(fname),
                ))
            else:
                if line_fields[fname].get("type") in ("many2one", "one2many", "many2many", "monetary"):
                    typecast = sql.SQL('integer')
                elif line_fields[fname].get("type") == "datetime":
                    typecast = sql.SQL('date')
                elif line_fields[fname].get("type") == "selection":
                    typecast = sql.SQL('text')
                else:
                    typecast = sql.SQL(line_fields[fname].get("type"))
                selected_fields.append(sql.SQL('cast(NULL AS {typecast}) AS "account_move_line.{fname}"').format(
                    typecast=typecast,
                    fname=sql.SQL(fname),
                ))

        query = sql.SQL("""
            -- Create a temporary table, dropping not null constraints because we're not filling those columns
            CREATE TEMPORARY TABLE IF NOT EXISTS analytic_temp_account_move_line () inherits (account_move_line) ON COMMIT DROP;
            ALTER TABLE analytic_temp_account_move_line NO INHERIT account_move_line;
            ALTER TABLE analytic_temp_account_move_line ALTER COLUMN move_id DROP NOT NULL;
            ALTER TABLE analytic_temp_account_move_line ALTER COLUMN currency_id DROP NOT NULL;

            INSERT INTO analytic_temp_account_move_line ({all_fields})
            SELECT {table}
            FROM (SELECT * FROM account_analytic_line WHERE general_account_id IS NOT NULL) AS account_analytic_line
        """).format(
            all_fields=sql.SQL(', ').join(sql.Identifier(fname) for fname in stored_fields),
            table=sql.SQL(', ').join(selected_fields),
        )

        # TODO gawa need to do the auditing of the lines
        # TODO gawa try to reduce query on analytic lines

        self.env.cr.execute(query)

    def _query_get(self, options, date_scope, domain=None):
        # Override to add the context key which will eventually trigger the shadowing of the table
        context_self = self.with_context(account_report_analytic_groupby=options.get('analytic_groupby_option'))
        return super(AccountReport, context_self)._query_get(options, date_scope, domain)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _where_calc(self, domain, active_test=True):
        """ In case we need an analytic column in an account_report, we shadow the account_move_line table
        with a temp table filled with analytic data, that will be used for the analytic columns.
        We do it in this function to only create and fill it once for all computations of a report.
        The following analytic columns and computations will just query the shadowed table instead of the real one.
        """
        query = super()._where_calc(domain, active_test)
        if self.env.context.get('account_report_analytic_groupby'):
            self.env['account.report']._prepare_lines_for_analytic_groupby()
            query._tables['account_move_line'] = 'analytic_temp_account_move_line'
        return query
