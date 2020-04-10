# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrContractSalaryAdvantage(models.Model):
    _name = 'hr.contract.salary.advantage'
    _description = 'Salary Package Advantage'
    _order = 'sequence'

    def _get_field_domain(self):
        fields_ids = self.env['hr.contract']._get_advantage_fields()
        return [
            ('model', '=', 'hr.contract'),
            ('name', 'in', fields_ids),
            ('ttype', 'not in', ('one2many', 'many2one', 'many2many'))]

    def _get_binary_field_domain(self):
        return [
            ('model', '=', 'hr.contract'),
            ('ttype', '=', 'binary')]

    name = fields.Char(translate=True)
    active = fields.Boolean(default=True)
    res_field_id = fields.Many2one(
        'ir.model.fields', string="Advantage Field", domain=_get_field_domain, ondelete='cascade', required=True,
        help='Contract field linked to this advantage')
    cost_res_field_id = fields.Many2one(
        'ir.model.fields', string="Cost Field", domain=_get_field_domain, ondelete='cascade',
        help="Contract field linked to this advantage cost. If not set, the advantage won't be taken into account when computing the employee budget.")
    # LUL rename into field and cost_field to be consistent with fold_field and manual_field?
    field = fields.Char(related="res_field_id.name", readonly=True)
    cost_field = fields.Char(related="cost_res_field_id.name", string="Cost Field Name", readonly=True)
    sequence = fields.Integer(default=100)
    advantage_type_id = fields.Many2one(
        'hr.contract.salary.advantage.type', required=True,
        default=lambda self: self.env.ref('hr_contract_salary.l10n_be_monthly_benefit', raise_if_not_found=False))
    folded = fields.Boolean()
    fold_label = fields.Char()
    fold_res_field_id = fields.Many2one(
        'ir.model.fields', domain=_get_field_domain, ondelete='cascade',
        help='Contract field used to fold this advantage.')
    fold_field = fields.Char(related='fold_res_field_id.name', string="Fold Field Name", readonly=True)
    manual_res_field_id = fields.Many2one(
        'ir.model.fields', domain=_get_field_domain, ondelete='cascade',
        help='Contract field used to manually encode an advantage value.')
    manual_field = fields.Char(related='manual_res_field_id.name', string="Manual Field Name", readonly=True)
    country_id = fields.Many2one('res.country')
    structure_type_id = fields.Many2one('hr.payroll.structure.type', string="Salary Structure Type", required=True)
    icon = fields.Char()
    display_type = fields.Selection(selection=[
        ('always', 'Always Selected'),
        ('dropdown', 'Dropdown'),
        ('slider', 'Slider'),
        ('radio', 'Radio Buttons'),
        ('manual', 'Manual Input'),
    ])
    impacts_net_salary = fields.Boolean(default=True)
    description = fields.Char('Description')
    slider_min = fields.Integer()
    slider_max = fields.Integer()
    value_ids = fields.One2many('hr.contract.salary.advantage.value', 'advantage_id')
    hide_description = fields.Boolean(help="Hide the description if the advantage is not taken.")
    requested_documents_field_ids = fields.Many2many('ir.model.fields', domain=_get_binary_field_domain, string="Requested Documents")
    requested_documents = fields.Char(compute='_compute_requested_documents', string="Requested Documents Fields", compute_sudo=True)
    uom = fields.Selection([
        ('days', 'Days'),
        ('percent', 'Percent'),
        ('currency', 'Currency')], string="Advantage Unit of Measure", default='currency')

    activity_type_id = fields.Many2one('mail.activity.type', string='Activity Type', help="The type of activity that will be created automatically on the contract if this advantage is chosen by the employee.")
    activity_creation = fields.Selection([('countersigned', 'Contract is countersigned'), ('running', 'Employee signs his contract')], default='countersigned', help="The benefit is created when the employee signs his contract at the end of the salary configurator or when the HR manager countersigns the contract.")
    activity_creation_type = fields.Selection([('always', 'When the advantage is set'), ('onchange', 'When the advantage is modified')], default='always', help="Choose whether to create a next activity each time that the advantage is taken by the employee or on modification only.")
    activity_responsible_id = fields.Many2one('res.users', 'Assigned to')

    _sql_constraints = [
        (
            'required_fold_res_field_id',
            'check (folded = FALSE OR (folded = TRUE AND fold_res_field_id IS NOT NULL))',
            'A folded field is required'
        )
    ]

    @api.depends('requested_documents_field_ids')
    def _compute_requested_documents(self):
        for advantage in self:
            advantage.requested_documents = ','.join(advantage.requested_documents_field_ids.mapped('name'))

class HrContractSalaryAdvantageType(models.Model):
    _name = 'hr.contract.salary.advantage.type'
    _description = 'Contract Advantage Type'
    _order = 'sequence'

    name = fields.Char()
    periodicity = fields.Selection([
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], default='monthly')
    sequence = fields.Integer(default=100)


class HrContractSalaryAdvantageValue(models.Model):
    _name = 'hr.contract.salary.advantage.value'
    _description = 'Contract Advantage Value'

    name = fields.Char(translate=True)
    advantage_id = fields.Many2one('hr.contract.salary.advantage')
    value = fields.Char(required=True)
    color = fields.Selection(selection=[
        ('green', 'Green'),
        ('red', 'Red')], string="Color", default="green", required=True)
    hide_description = fields.Boolean()
