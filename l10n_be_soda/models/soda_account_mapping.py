from odoo import api, fields, models


class SodaAccountMapping(models.Model):
    _name = 'soda.account.mapping'
    _description = 'SODA Account Mapping'
    _order = 'code, company_id'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    code = fields.Char('SODA Account', required=True)
    name = fields.Char('SODA Label', required=True)
    account_id = fields.Many2one(
        'account.account',
        string='Mapped Account',
        compute='_compute_account_id',
        readonly=False,
        store=True,
        check_company=True
    )

    _sql_constraints = [
        ('code_company_uniq', 'unique (code, company_id)', 'The code of the SODA account must be unique per company')
    ]

    @api.depends('code', 'company_id')
    def _compute_account_id(self):
        for mapping in self:
            mapping.account_id = self.env['account.account'].search(
                [('code', 'like', f'{mapping.code}%'), ('company_id', '=', self.company_id.id)],
                limit=1
            )

    @api.model
    def find_or_create_mapping_entries(self, soda_code_to_name_mapping, company_id):
        """Find account mappings for the provided SODA codes and/or create new ones when mappings for some SODA codes
        do not exist yet.

        :param soda_code_to_name_mapping: a dict mapping SODA codes to their names
        :param company_id: the company for which to find or create the entries
        :return: a recordset of soda.account.mapping entries for the given SODA codes
        """
        soda_account_codes = list(soda_code_to_name_mapping.keys())
        # Find existing account mappings for the provided SODA codes
        soda_account_mappings = self.search([
            ('company_id', '=', company_id.id),
            ('code', 'in', soda_account_codes),
        ])
        soda_account_mapping_codes = set(soda_account_mappings.mapped('code'))
        new_soda_account_mappings = []
        for code, name in soda_code_to_name_mapping.items():
            # For each SODA code where there's not mapping yet, we create a new one
            if code not in soda_account_mapping_codes:
                soda_account_mapping_codes.add(code)
                new_soda_account_mappings.append({
                    'code': code,
                    'name': name,
                    'company_id': company_id.id,
                })
        soda_account_mappings |= self.create(new_soda_account_mappings)
        return soda_account_mappings
