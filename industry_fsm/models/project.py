# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from ast import literal_eval
from datetime import timedelta, datetime

from odoo import fields, models, api, _
from odoo.exceptions import UserError, AccessError


class Project(models.Model):
    _inherit = "project.project"

    @api.model
    def default_get(self, fields):
        """ Pre-fill timesheet product as "Time" data product when creating new project allowing billable tasks by default. """
        result = super(Project, self).default_get(fields)
        if 'timesheet_product_id' in fields and result.get('allow_billable') and not result.get('timesheet_product_id'):
            default_product = self.env.ref('industry_fsm.fsm_time_product', False)
            if default_product:
                result['timesheet_product_id'] = default_product.id
        return result

    product_template_ids = fields.Many2many('product.template', string="Allowed Products", help="Products allowed to be added on this Task's Material.")
    allow_billable = fields.Boolean('Allow to bill Tasks', help='Enables the creation of unrelated Quotations from tasks, the addition of products on tasks and the billing of the task.')
    timesheet_product_id = fields.Many2one('product.product', string='Timesheet Product', domain=[('type', '=', 'service'), ('invoice_policy', '=', 'delivery'), ('service_type', '=', 'timesheet')], help='Select a Service product with which you would like to bill your time spent on tasks.')

    _sql_constraints = [
        ('timesheet_product_required_if_billable', "CHECK((allow_billable = 't' AND timesheet_product_id IS NOT NULL) OR (allow_billable = 'f'))", 'The timesheet product is required when the task can be billed.'),
    ]


class Task(models.Model):
    _inherit = "project.task"

    def _default_fsm_state(self):
        if self.env.context.get('fsm_mode'):
            return 'draft'

    def _default_planned_date_begin(self):
        if self.env.context.get('fsm_mode'):
            return datetime.now()

    def _default_planned_date_end(self):
        if self.env.context.get('fsm_mode'):
            return datetime.now() + timedelta(hours=1)

    allow_billable = fields.Boolean(related='project_id.allow_billable')
    planning_overlap = fields.Integer(compute='_compute_planning_overlap')
    quotation_count = fields.Integer(compute='_compute_quotation_count')
    material_line_ids = fields.One2many('product.task.map', 'task_id')
    product_template_ids = fields.Many2many(related='project_id.product_template_ids')
    material_line_product_count = fields.Integer(compute='_compute_material_line_product_count')
    material_line_total_price = fields.Integer(compute='_compute_material_line_total_price')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    fsm_state = fields.Selection([('draft', 'New'), ('validated', 'Validated'), ('sold', 'Sold')], default=_default_fsm_state, string='Status', readonly=True)
    partner_email = fields.Char(related='partner_id.email', string='Customer Email', readonly=False)
    partner_phone = fields.Char(related='partner_id.phone', readonly=False)
    partner_mobile = fields.Char(related='partner_id.mobile', readonly=False)
    partner_zip = fields.Char(related='partner_id.zip', readonly=False)
    partner_city = fields.Char(related='partner_id.city', readonly=False)
    planned_date_begin = fields.Datetime(default=_default_planned_date_begin)
    planned_date_end = fields.Datetime(default=_default_planned_date_end)
    user_id = fields.Many2one(group_expand='_read_group_user_ids')
    invoice_count = fields.Integer("Number of invoices", related='sale_order_id.invoice_count')

    @api.model
    def _read_group_user_ids(self, users, domain, order):
        if self.env.context.get('fsm_mode'):
            search_domain = ['|', ('id', 'in', users.ids), ('groups_id', 'in', self.env.ref('industry_fsm.group_fsm_user').id)]
            return users.search(search_domain, order=order)
        return users

    @api.depends('planned_date_begin', 'planned_date_end', 'user_id')
    def _compute_planning_overlap(self):
        for task in self:
            domain = [('allow_planning', '=', True),
                      ('user_id', '=', task.user_id.id),
                      ('planned_date_begin', '<', task.planned_date_end),
                      ('planned_date_end', '>', task.planned_date_begin)]
            current_id = task._origin.id
            if current_id:
                domain.append(('id', '!=', current_id))
            overlap = self.env['project.task'].search_count(domain)
            task.planning_overlap = overlap

    def _compute_quotation_count(self):
        quotation_data = self.env['sale.order'].read_group([('state', '!=', 'cancel'), ('task_id', 'in', self.ids)], ['task_id'], ['task_id'])
        mapped_data = dict([(q['task_id'][0], q['task_id_count']) for q in quotation_data])
        for task in self:
            task.quotation_count = mapped_data.get(task.id, 0)

    def _compute_material_line_product_count(self):
        material_data = self.env['product.task.map'].read_group([('task_id', 'in', self.ids)], ['quantity', 'task_id'], ['task_id'])
        mapped_quantities = dict([(m['task_id'][0], m['quantity']) for m in material_data])
        for task in self:
            task.material_line_product_count = mapped_quantities.get(task.id, 0)

    def _compute_material_line_total_price(self):
        for task in self:
            total_price = sum(task.material_line_ids.mapped(lambda line: line.quantity * line.product_id.lst_price))
            task.material_line_total_price = total_price

    # ---------------------------------------------------------
    # Actions
    # ---------------------------------------------------------

    def action_view_timesheets(self):
        kanban_view = self.env.ref('hr_timesheet.view_kanban_account_analytic_line')
        form_view = self.env.ref('industry_fsm.timesheet_view_form')
        tree_view = self.env.ref('industry_fsm.timesheet_view_tree_user_inherit')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Time'),
            'res_model': 'account.analytic.line',
            'view_mode': 'list,form,kanban',
            'views': [(tree_view.id, 'list'), (kanban_view.id, 'kanban'), (form_view.id, 'form')],
            'domain': [('task_id', '=', self.id), ('project_id', '!=', False)],
            'context': {
                'fsm_mode': True,
                'default_project_id': self.project_id.id,
                'default_task_id': self.id,
            }
        }

    def action_view_invoices(self):
        invoices = self.mapped('sale_order_id.invoice_ids')
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        action['domain'] = [('id', 'in', invoices.ids)]
        # prevent view with onboarding banner
        list_view = self.env.ref('account.view_move_tree')
        form_view = self.env.ref('account.view_move_form')
        action['views'] = [[list_view.id, 'list'], [form_view.id, 'form']]

        return action

    def action_fsm_tasks(self):
        action = self.env.ref('industry_fsm.project_task_action_fsm').read()[0]
        context = literal_eval(action.get('context', "{}"))

        # Workaround to avoid a read error on fsm project when we are not in the main company
        fsm_project = self.env.ref('industry_fsm.fsm_project', False)
        if fsm_project:
            try:
                fsm_project.check_access_rule('read')
                context['default_project_id'] = fsm_project.id
            except AccessError:
                pass
        context['fsm_mode'] = True  # force the context key, as all the state flow depends on it
        action['context'] = context

        # change the help message
        if self.env.user.has_group('industry_fsm.group_fsm_manager'):
            action['help'] = _(
                """<p class='o_view_nocontent_smiling_face'>No future Tasks planned</p>
                <p>You can go to the <a class="btn btn-link pr-0 pl-0" type="action" name="%s">Planning</a>
                Menu and create Tasks for your Workers or create one for yourself by clicking on Create.</p>
                """) % (self.env.ref('project_enterprise.project_task_action_planning_groupby_user').id)
        else:
            action['help'] = _(
                """ <p class='o_view_nocontent_smiling_face'>No future Tasks planned</p>
                <p>You can create one for yourself by clicking on Create.</p>
                """
            )
        return action

    def action_fsm_create_quotation(self):
        view_form_id = self.env.ref('sale.view_order_form').id
        action = self.env.ref('sale.action_quotations').read()[0]
        action.update({
            'views': [(view_form_id, 'form')],
            'view_mode': 'form',
            'name': self.name,
            'context': {
                'fsm_mode': True,
                'form_view_initial_mode': 'edit',
                'default_partner_id': self.partner_id.id,
                'default_state': 'draft',
                'default_task_id': self.id
            },
        })
        return action

    def action_fsm_view_quotations(self):
        action = self.env.ref('sale.action_quotations').read()[0]
        action.update({
            'name': self.name,
            'domain': [('task_id', '=', self.id)],
            'context': {
                'fsm_mode': True,
                'default_task_id': self.id,
                'default_partner_id': self.partner_id.id},
        })
        if self.quotation_count == 1:
            action['res_id'] = self.env['sale.order'].search([('task_id', '=', self.id)]).id
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
        return action

    def action_fsm_view_material(self):
        kanban_view = self.env.ref('industry_fsm.view_product_product_kanban_material')
        domain = [('product_tmpl_id', 'in', self.product_template_ids.ids)] if self.product_template_ids else False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Products'),
            'res_model': 'product.product',
            'views': [(kanban_view.id, 'kanban')],
            'domain': domain,
            'context': {
                'fsm_mode': True,
                'default_task_id': self.id,
                'pricelist': self.partner_id.property_product_pricelist.id if self.partner_id else False,
                'partner': self.partner_id.id if self.partner_id else False,
            }
        }

    def action_make_billable(self):
        """ Override to set the selected timesheet_product_id by default in the
            'create sale order from task' wizard
        """
        action = super(Task, self).action_make_billable()
        product = self.project_id.timesheet_product_id
        if product:
            action['context']['default_product_id'] = product.id
        return action

    def action_fsm_validate(self):
        """ Moves Task to next stage.
            If allow billable on task, timesheet product set on project and user has privileges :
            Create SO confirmed with time and material.
        """
        for task in self:
            # determine closed stage for task
            closed_stage = task.project_id.type_ids.filtered(lambda stage: stage.is_closed)
            if not closed_stage and len(task.project_id.type_ids) > 1:  # project without stage (or with only one)
                closed_stage = task.project_id.type_ids[-1]

            values = {'fsm_state': 'validated'}
            if closed_stage:
                values['stage_id'] = closed_stage.id

            task.write(values)

    def action_fsm_create_invoice(self):
        # update sales order with material lines
        if self.allow_billable and self.project_id.timesheet_product_id:
            if self.sale_line_id:
                self._fsm_add_material_to_sale_order()
            else:
                self._fsm_create_sale_order()
        # redirect create invoice wizard (of the Sales Order)
        action = self.env.ref('sale.action_view_sale_advance_payment_inv').read()[0]
        context = literal_eval(action.get('context', "{}"))
        context.update({
            'active_model': 'sale.order',
            'active_id': self.sale_order_id.id,
            'active_ids': self.sale_order_id.ids,
        })
        action['context'] = context
        return action

    # ---------------------------------------------------------
    # Business Methods
    # ---------------------------------------------------------

    def _fsm_create_sale_order(self):
        """ Create the SO from the task, sell the timesheet with the 'service product' of the SO, and add the material lines """
        if not self.partner_id:
            raise UserError(_('The FSM task must have a customer set to be sold.'))

        sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'analytic_account_id': self.project_id.analytic_account_id.id,
        })
        sale_order_line = self.env['sale.order.line'].create({
            'order_id': sale_order.id,
            'product_id': self.project_id.timesheet_product_id.id,
            'project_id': self.project_id.id,
            'task_id': self.id,
            'product_uom_qty': self.total_hours_spent,
            'product_uom': self.project_id.timesheet_product_id.uom_id.id,
        })

        self.write({
            'sale_line_id': sale_order_line.id,
            'fsm_state': 'sold',
        })

        # assign SOL to timesheets
        self.env['account.analytic.line'].search([
            ('task_id', '=', self.id),
            ('so_line', '=', False),
            ('project_id', '!=', False)
        ]).write({
            'so_line': sale_order_line.id
        })

        self._fsm_add_material_to_sale_order()
        sale_order.action_confirm()
        return sale_order

    def _fsm_add_material_to_sale_order(self):
        sale_order = self.sale_order_id
        if sale_order:
            for line in self.material_line_ids:
                existing_line = self.env['sale.order.line'].search([('order_id', '=', sale_order.id), ('product_id', '=', line.product_id.id)], limit=1)
                if existing_line:
                    existing_line.write({'product_uom_qty': existing_line.product_uom_qty + line.quantity})
                else:
                    vals = {
                        'order_id': sale_order.id,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.quantity,
                        'product_uom': line.product_id.uom_id.id
                    }
                    if line.product_id.invoice_policy == 'delivery' and line.product_id.service_type == 'manual':
                        vals['qty_delivered'] = line.quantity
                    self.env['sale.order.line'].create(vals)
        return sale_order
