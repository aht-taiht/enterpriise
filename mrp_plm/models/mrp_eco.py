# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast

from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.exceptions import UserError


class MrpEcoType(models.Model):
    _name = "mrp.eco.type"
    _description = 'ECO Type'
    _inherit = ['mail.alias.mixin', 'mail.thread']

    name = fields.Char('Name', required=True, translate=True)
    sequence = fields.Integer('Sequence')
    nb_ecos = fields.Integer('ECOs', compute='_compute_nb')
    nb_approvals = fields.Integer('Waiting Approvals', compute='_compute_nb')
    nb_approvals_my = fields.Integer('Waiting my Approvals', compute='_compute_nb')
    nb_validation = fields.Integer('To Apply', compute='_compute_nb')
    color = fields.Integer('Color', default=1)
    stage_ids = fields.One2many('mrp.eco.stage', 'type_id', 'Stages')

    def _compute_nb(self):
        # TDE FIXME: this seems not good for performances, to check (replace by read_group later on)
        MrpEco = self.env['mrp.eco']
        for eco_type in self:
            eco_type.nb_ecos = MrpEco.search_count([
                ('type_id', '=', eco_type.id), ('state', '!=', 'done')
            ])
            eco_type.nb_validation = MrpEco.search_count([
                ('stage_id.type_id', '=', eco_type.id),
                ('stage_id.allow_apply_change', '=', True),
                ('state', '=', 'progress')
            ])
            eco_type.nb_approvals = MrpEco.search_count([
                ('stage_id.type_id', '=', eco_type.id),
                ('approval_ids.status', '=', 'none')
            ])
            eco_type.nb_approvals_my = MrpEco.search_count([
                ('stage_id.type_id', '=', eco_type.id),
                ('approval_ids.status', '=', 'none'),
                ('approval_ids.required_user_ids', '=', self.env.user.id)
            ])

    def _alias_get_creation_values(self):
        values = super(MrpEcoType, self)._alias_get_creation_values()
        values['alias_model_id'] = self.env['ir.model']._get('mrp.eco').id
        if self.id:
            values['alias_defaults'] = defaults = ast.literal_eval(self.alias_defaults or "{}")
            defaults['type_id'] = self.id
        return values


class MrpEcoApprovalTemplate(models.Model):
    _name = "mrp.eco.approval.template"
    _order = "sequence"
    _description = 'ECO Approval Template'

    name = fields.Char('Role', required=True)
    sequence = fields.Integer('Sequence')
    approval_type = fields.Selection([
        ('optional', 'Approves, but the approval is optional'),
        ('mandatory', 'Is required to approve'),
        ('comment', 'Comments only')], 'Approval Type',
        default='mandatory', required=True)
    user_ids = fields.Many2many('res.users', string='Users', required=True)
    stage_id = fields.Many2one('mrp.eco.stage', 'Stage', required=True)


class MrpEcoApproval(models.Model):
    _name = "mrp.eco.approval"
    _description = 'ECO Approval'
    _order = 'approval_date desc'

    eco_id = fields.Many2one(
        'mrp.eco', 'ECO',
        ondelete='cascade', required=True)
    approval_template_id = fields.Many2one(
        'mrp.eco.approval.template', 'Template',
        ondelete='cascade', required=True)
    name = fields.Char('Role', related='approval_template_id.name', store=True, readonly=False)
    user_id = fields.Many2one(
        'res.users', 'Approved by')
    required_user_ids = fields.Many2many(
        'res.users', string='Requested Users', related='approval_template_id.user_ids', readonly=False)
    template_stage_id = fields.Many2one(
        'mrp.eco.stage', 'Approval Stage',
        related='approval_template_id.stage_id', store=True, readonly=False)
    eco_stage_id = fields.Many2one(
        'mrp.eco.stage', 'ECO Stage',
        related='eco_id.stage_id', store=True, readonly=False)
    status = fields.Selection([
        ('none', 'Not Yet'),
        ('comment', 'Commented'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')], string='Status',
        default='none', required=True)
    approval_date = fields.Datetime('Approval Date')
    is_closed = fields.Boolean()
    is_approved = fields.Boolean(
        compute='_compute_is_approved', store=True)
    is_rejected = fields.Boolean(
        compute='_compute_is_rejected', store=True)

    @api.depends('status', 'approval_template_id.approval_type')
    def _compute_is_approved(self):
        for rec in self:
            if rec.approval_template_id.approval_type == 'mandatory':
                rec.is_approved = rec.status == 'approved'
            else:
                rec.is_approved = True

    @api.depends('status', 'approval_template_id.approval_type')
    def _compute_is_rejected(self):
        for rec in self:
            if rec.approval_template_id.approval_type == 'mandatory':
                rec.is_rejected = rec.status == 'rejected'
            else:
                rec.is_rejected = False


class MrpEcoStage(models.Model):
    _name = 'mrp.eco.stage'
    _description = 'ECO Stage'
    _order = "sequence, id"
    _fold_name = 'folded'

    @api.model
    def _get_sequence(self):
        others = self.search([('sequence','<>',False)], order='sequence desc', limit=1)
        if others:
            return (others[0].sequence or 0) + 1
        return 1

    name = fields.Char('Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=_get_sequence)
    folded = fields.Boolean('Folded in kanban view')
    allow_apply_change = fields.Boolean(string='Allow to apply changes', help='Allow to apply changes from this stage.')
    final_stage = fields.Boolean(string='Final Stage', help='Once the changes are applied, the ECOs will be moved to this stage.')
    type_id = fields.Many2one('mrp.eco.type', 'Type', required=True, default=lambda self: self.env['mrp.eco.type'].search([], limit=1))
    approval_template_ids = fields.One2many('mrp.eco.approval.template', 'stage_id', 'Approvals')
    approval_roles = fields.Char('Approval Roles', compute='_compute_approvals', store=True)
    is_blocking = fields.Boolean('Blocking Stage', compute='_compute_is_blocking', store=True)

    @api.depends('approval_template_ids.name')
    def _compute_approvals(self):
        for rec in self:
            rec.approval_roles = ', '.join(rec.approval_template_ids.mapped('name'))

    @api.depends('approval_template_ids.approval_type')
    def _compute_is_blocking(self):
        for rec in self:
            rec.is_blocking = any(template.approval_type == 'mandatory' for template in rec.approval_template_ids)


class MrpEco(models.Model):
    _name = 'mrp.eco'
    _description = 'Engineering Change Order (ECO)'
    _inherit = ['mail.thread.cc', 'mail.activity.mixin']

    @api.model
    def _get_type_selection(self):
        types = [
            ('product', _('Product Only')),
            ('bom', _('Bill of Materials'))]
        if self.user_has_groups('mrp.group_mrp_routings'):
            types += [('routing', _('Routing')), ('both', _('BoM and Routing'))]
        return types

    name = fields.Char('Reference', copy=False, required=True)
    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user, tracking=True, check_company=True)
    type_id = fields.Many2one('mrp.eco.type', 'Type', required=True)
    stage_id = fields.Many2one(
        'mrp.eco.stage', 'Stage', ondelete='restrict', copy=False, domain="[('type_id', '=', type_id)]",
        group_expand='_read_group_stage_ids', tracking=True,
        default=lambda self: self.env['mrp.eco.stage'].search([('type_id', '=', self._context.get('default_type_id'))], limit=1))
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    tag_ids = fields.Many2many('mrp.eco.tag', string='Tags')
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'High')], string='Priority', tracking=True,
        index=True)
    note = fields.Text('Note')
    effectivity = fields.Selection([
        ('asap', 'As soon as possible'),
        ('date', 'At Date')], string='Effectivity',  # Is this English ?
        compute='_compute_effectivity', inverse='_set_effectivity', store=True,
        help='Date on which the changes should be applied. For reference only.')
    effectivity_date = fields.Datetime('Effectivity Date', tracking=True, help="For reference only.")
    approval_ids = fields.One2many('mrp.eco.approval', 'eco_id', 'Approvals', help='Approvals by stage')

    state = fields.Selection([
        ('confirmed', 'To Do'),
        ('progress', 'In Progress'),
        ('rebase', 'Rebase'),
        ('conflict', 'Conflict'),
        ('done', 'Done')], string='Status',
        copy=False, default='confirmed', readonly=True, required=True)
    user_can_approve = fields.Boolean(
        'Can Approve', compute='_compute_user_approval',
        help='Technical field to check if approval by current user is required')
    user_can_reject = fields.Boolean(
        'Can Reject', compute='_compute_user_approval',
        help='Technical field to check if reject by current user is possible')
    kanban_state = fields.Selection([
        ('normal', 'In Progress'),
        ('done', 'Approved'),
        ('blocked', 'Blocked')], string='Kanban State',
        copy=False, compute='_compute_kanban_state', store=True)
    allow_change_stage = fields.Boolean(
        'Allow Change Stage', compute='_compute_allow_change_stage')
    allow_apply_change = fields.Boolean(
        'Show Apply Change', compute='_compute_allow_apply_change')

    product_tmpl_id = fields.Many2one('product.template', "Product", check_company=True)
    type = fields.Selection(selection=_get_type_selection, string='Apply on',
        default='product', required=True)
    bom_id = fields.Many2one(
        'mrp.bom', "Bill of Materials",
        domain="[('product_tmpl_id', '=', product_tmpl_id)]", check_company=True)  # Should at least have bom or routing on which it is applied?
    new_bom_id = fields.Many2one(
        'mrp.bom', 'New Bill of Materials',
        copy=False)
    new_bom_revision = fields.Integer('BoM Revision', related='new_bom_id.version', store=True, readonly=False)
    routing_id = fields.Many2one('mrp.routing', "Routing", check_company=True)
    new_routing_id = fields.Many2one(
        'mrp.routing', 'New Routing',
        copy=False, check_company=True)
    new_routing_revision = fields.Integer('Routing Revision', related='new_routing_id.version', store=True, readonly=False)
    bom_change_ids = fields.One2many(
        'mrp.eco.bom.change', 'eco_id', string="ECO BoM Changes",
        compute='_compute_bom_change_ids', help='Difference between old BoM and new BoM revision', store=True)
    bom_rebase_ids = fields.One2many('mrp.eco.bom.change', 'rebase_id', string="BoM Rebase")
    routing_change_ids = fields.One2many(
        'mrp.eco.routing.change', 'eco_id', string="ECO Routing Changes",
        compute='_compute_routing_change_ids', help='Difference between old routing and new routing revision', store=True)
    mrp_document_count = fields.Integer('# Attachments', compute='_compute_attachments')
    mrp_document_ids = fields.One2many(
        'mrp.document', 'res_id', string='Attachments',
        auto_join=True, domain=lambda self: [('res_model', '=', self._name)])
    displayed_image_id = fields.Many2one(
        'mrp.document', 'Displayed Image',
        domain="[('res_model', '=', 'mrp.eco'), ('res_id', '=', id), ('mimetype', 'ilike', 'image')]")
    displayed_image_attachment_id = fields.Many2one('ir.attachment', related='displayed_image_id.ir_attachment_id', readonly=False)
    color = fields.Integer('Color')
    active = fields.Boolean('Active', default=True, help="If the active field is set to False, it will allow you to hide the engineering change order without removing it.")
    current_bom_id = fields.Many2one('mrp.bom', string="New Bom")
    previous_change_ids = fields.One2many('mrp.eco.bom.change', 'eco_rebase_id', string="Previous ECO Changes", compute='_compute_previous_bom_change', store=True)

    def _compute_attachments(self):
        for p in self:
            p.mrp_document_count = len(p.mrp_document_ids)

    @api.depends('effectivity_date')
    def _compute_effectivity(self):
        for eco in self:
            eco.effectivity = 'date' if eco.effectivity_date else 'asap'

    def _set_effectivity(self):
        for eco in self:
            if eco.effectivity == 'asap':
                eco.effectivity_date = False

    def _is_conflict(self, new_bom_lines, changes=None):
        # Find rebase lines having conflict or not.
        reb_conflicts = self.env['mrp.eco.bom.change']
        for reb_line in changes:
            new_line = new_bom_lines.get(reb_line.product_id, None)
            if new_line and (reb_line.old_operation_id, reb_line.old_uom_id, reb_line.old_product_qty) != (new_line.operation_id, new_line.product_uom_id, new_line.product_qty):
                reb_conflicts |= reb_line
        reb_conflicts.write({'conflict': True})
        return reb_conflicts

    def _get_difference_bom_lines(self, old_bom, new_bom):
        # Return difference lines from two bill of material.
        new_bom_commands = [(5,)]
        old_bom_lines = dict(((line.product_id, tuple(line.bom_product_template_attribute_value_ids.ids)), line) for line in old_bom.bom_line_ids)
        if self.new_bom_id:
            for line in new_bom.bom_line_ids:
                old_line = old_bom_lines.pop((line.product_id, tuple(line.bom_product_template_attribute_value_ids.ids)), None)
                if old_line and (line.product_uom_id, line.product_qty, line.operation_id) != (old_line.product_uom_id, old_line.product_qty, old_line.operation_id):
                    new_bom_commands += [(0, 0, {
                        'change_type': 'update',
                        'product_id': line.product_id.id,
                        'old_uom_id': old_line.product_uom_id.id,
                        'new_uom_id': line.product_uom_id.id,
                        'old_operation_id': old_line.operation_id.id,
                        'new_operation_id': line.operation_id.id,
                        'new_product_qty': line.product_qty,
                        'old_product_qty': old_line.product_qty})]
                elif not old_line:
                    new_bom_commands += [(0, 0, {
                        'change_type': 'add',
                        'product_id': line.product_id.id,
                        'new_uom_id': line.product_uom_id.id,
                        'new_operation_id': line.operation_id.id,
                        'new_product_qty': line.product_qty
                    })]
            for key, old_line in old_bom_lines.items():
                new_bom_commands += [(0, 0, {
                    'change_type': 'remove',
                    'product_id': old_line.product_id.id,
                    'old_uom_id': old_line.product_uom_id.id,
                    'old_operation_id': old_line.operation_id.id,
                    'old_product_qty': old_line.product_qty,
                })]
        return new_bom_commands

    def rebase(self, old_bom_lines, new_bom_lines, rebase_lines):
        """
        This method will apply changes in new revision of BoM
            old_bom_lines : Previous BoM or Old BoM version lines.
            new_bom_lines : New BoM version lines.
            rebase_lines  : Changes done in previous version
        """
        for reb_line in rebase_lines:
            new_bom_line = new_bom_lines.get(reb_line.product_id, None)
            if new_bom_line:
                if new_bom_line.product_qty + reb_line.upd_product_qty > 0.0:
                    # Update line if it exist in new bom.
                    new_bom_line.write({'product_qty': new_bom_line.product_qty + reb_line.upd_product_qty, 'operation_id': reb_line.new_operation_id.id, 'product_uom_id': reb_line.new_uom_id.id})
                else:
                    # Unlink lines if old bom removed lines
                    new_bom_line.unlink()
            else:
                # Add bom line in new bom for rebase.
                old_line = old_bom_lines.get(reb_line.product_id, None)
                if old_line:
                    old_line.copy({'bom_id': self.new_bom_id.id})
        return True

    def apply_rebase(self):
        """ Apply rebase changes in new version of BoM """
        self.ensure_one()
        # Rebase logic applied..
        vals = {'state': 'progress'}
        if self.bom_rebase_ids:
            new_bom_lines = dict(((line.product_id), line) for line in self.new_bom_id.bom_line_ids)
            if self._is_conflict(new_bom_lines, self.bom_rebase_ids):
                return self.write({'state': 'conflict'})
            else:
                old_bom_lines = dict(((line.product_id), line) for line in self.bom_id.bom_line_ids)
                self.rebase(old_bom_lines, new_bom_lines, self.bom_rebase_ids)
                # Remove all rebase line of current eco.
                self.bom_rebase_ids.unlink()
        if self.previous_change_ids:
            new_bom_lines = dict(((line.product_id), line) for line in self.new_bom_id.bom_line_ids)
            if self._is_conflict(new_bom_lines, self.previous_change_ids):
                return self.write({'state': 'conflict'})
            else:
                new_activated_bom_lines = dict(((line.product_id), line) for line in self.current_bom_id.bom_line_ids)
                self.rebase(new_activated_bom_lines, new_bom_lines, self.previous_change_ids)
                # Remove all rebase line of current eco.
                self.previous_change_ids.unlink()
        if self.current_bom_id:
            self.new_bom_id.write({'version': self.current_bom_id.version + 1, 'previous_bom_id': self.current_bom_id.id})
            vals.update({'bom_id': self.current_bom_id.id, 'current_bom_id': False})
        self.message_post(body=_('Successfully Rebased !'))
        return self.write(vals)

    @api.depends('bom_id.bom_line_ids', 'new_bom_id.bom_line_ids', 'new_bom_id.bom_line_ids.product_qty', 'new_bom_id.bom_line_ids.product_uom_id', 'new_bom_id.bom_line_ids.operation_id')
    def _compute_bom_change_ids(self):
        # Compute difference between old bom and new bom revision.
        for eco in self:
            eco.bom_change_ids = eco._get_difference_bom_lines(eco.bom_id, eco.new_bom_id)

    @api.depends('bom_id.bom_line_ids', 'current_bom_id.bom_line_ids', 'current_bom_id.bom_line_ids.product_qty', 'current_bom_id.bom_line_ids.product_uom_id', 'current_bom_id.bom_line_ids.operation_id')
    def _compute_previous_bom_change(self):
        for eco in self:
            if eco.current_bom_id:
                # Compute difference between old bom and newly activated bom.
                eco.previous_change_ids = eco._get_difference_bom_lines(eco.bom_id, eco.current_bom_id)
            else:
                eco.previous_change_ids = False

    @api.depends('routing_id.operation_ids', 'new_routing_id.operation_ids')
    def _compute_routing_change_ids(self):
        for rec in self:
            # TDE TODO: should we add workcenter logic ?
            new_routing_commands = [(5,)]
            old_routing_lines = dict(((op.workcenter_id,), op) for op in rec.routing_id.operation_ids)
            if rec.new_routing_id and rec.routing_id:
                for operation in rec.new_routing_id.operation_ids:
                    key = (operation.workcenter_id,)
                    old_op = old_routing_lines.pop(key, None)
                    if old_op and tools.float_compare(old_op.time_cycle_manual, operation.time_cycle_manual, 2) != 0:
                        new_routing_commands += [(0, 0, {
                            'change_type': 'update',
                            'workcenter_id': operation.workcenter_id.id,
                            'new_time_cycle_manual': operation.time_cycle_manual,
                            'old_time_cycle_manual': old_op.time_cycle_manual
                        })]
                    elif not old_op:
                        new_routing_commands += [(0, 0, {
                            'change_type': 'add',
                            'workcenter_id': operation.workcenter_id.id,
                            'new_time_cycle_manual': operation.time_cycle_manual
                        })]
                for key, old_op in old_routing_lines.items():
                    new_routing_commands += [(0, 0, {
                        'change_type': 'remove',
                        'workcenter_id': old_op.workcenter_id.id,
                        'old_time_cycle_manual': old_op.time_cycle_manual
                    })]
            rec.routing_change_ids = new_routing_commands

    def _compute_user_approval(self):
        for eco in self:
            is_required_approval = eco.stage_id.approval_template_ids.filtered(lambda x: x.approval_type in ('mandatory', 'optional') and self.env.user in x.user_ids)
            user_approvals = eco.approval_ids.filtered(lambda x: x.template_stage_id == eco.stage_id and x.user_id == self.env.user and not x.is_closed)
            last_approval = user_approvals.sorted(lambda a : a.create_date, reverse=True)[:1]
            eco.user_can_approve = is_required_approval and not last_approval.is_approved
            eco.user_can_reject = is_required_approval and not last_approval.is_rejected

    @api.depends('stage_id', 'approval_ids.is_approved', 'approval_ids.is_rejected')
    def _compute_kanban_state(self):
        """ State of ECO is based on the state of approvals for the current stage. """
        for rec in self:
            approvals = rec.approval_ids.filtered(lambda app:
                app.template_stage_id == rec.stage_id and not app.is_closed)
            if not approvals:
                rec.kanban_state = 'normal'
            elif all(approval.is_approved for approval in approvals):
                rec.kanban_state = 'done'
            elif any(approval.is_rejected for approval in approvals):
                rec.kanban_state = 'blocked'
            else:
                rec.kanban_state = 'normal'

    @api.depends('kanban_state', 'stage_id', 'approval_ids')
    def _compute_allow_change_stage(self):
        for rec in self:
            approvals = rec.approval_ids.filtered(lambda app: app.template_stage_id == rec.stage_id)
            if approvals:
                rec.allow_change_stage = rec.kanban_state == 'done'
            else:
                rec.allow_change_stage = rec.kanban_state in ['normal', 'done']

    @api.depends('state', 'stage_id.allow_apply_change')
    def _compute_allow_apply_change(self):
        for rec in self:
            rec.allow_apply_change = rec.stage_id.allow_apply_change and rec.state in ('confirmed', 'progress')

    @api.onchange('product_tmpl_id')
    def onchange_product_tmpl_id(self):
        if self.product_tmpl_id.bom_ids:
            self.bom_id = self.product_tmpl_id.bom_ids.ids[0]

    @api.onchange('bom_id', 'type')
    def onchange_bom_id(self):
        if self.type == 'both':
            self.routing_id = self.bom_id.routing_id

    @api.onchange('type_id')
    def onchange_type_id(self):
        self.stage_id = self.env['mrp.eco.stage'].search([('type_id', '=', self.type_id.id)], limit=1).id

    @api.model
    def create(self, vals):
        prefix = self.env['ir.sequence'].next_by_code('mrp.eco') or ''
        vals['name'] = '%s%s' % (prefix and '%s: ' % prefix or '', vals.get('name', ''))
        eco = super(MrpEco, self).create(vals)
        eco._create_approvals()
        return eco

    def write(self, vals):
        if vals.get('stage_id'):
            newstage = self.env['mrp.eco.stage'].browse(vals['stage_id'])
            # raise exception only if we increase the stage, not on decrease
            for eco in self:
                if eco.stage_id and ((newstage.sequence, newstage.id) > (eco.stage_id.sequence, eco.stage_id.id)):
                    if not eco.allow_change_stage:
                        raise UserError(_('You cannot change the stage, as approvals are still required.'))
                    has_blocking_stages = self.env['mrp.eco.stage'].search_count([
                        ('sequence', '>=', eco.stage_id.sequence),
                        ('sequence', '<=', newstage.sequence),
                        ('type_id', '=', eco.type_id.id),
                        ('id', 'not in', [eco.stage_id.id] + [vals['stage_id']]),
                        ('is_blocking', '=', True)])
                    if has_blocking_stages:
                        raise UserError(_('You cannot change the stage, as approvals are required in the process.'))
                if eco.stage_id != newstage:
                    eco.approval_ids.filtered(lambda x: x.status != 'none').write({'is_closed': True})
                    eco.approval_ids.filtered(lambda x: x.status == 'none').unlink()
        res = super(MrpEco, self).write(vals)
        if vals.get('stage_id'):
            self._create_approvals()
        return res

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """ Read group customization in order to display all the stages of the ECO type
        in the Kanban view, even if there is no ECO in that stage
        """
        search_domain = []
        if self._context.get('default_type_id'):
            search_domain = [('type_id', '=', self._context['default_type_id'])]

        stage_ids = stages._search(search_domain, order=order, access_rights_uid=SUPERUSER_ID)
        return stages.browse(stage_ids)

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        message = super(MrpEco, self).message_post(**kwargs)
        if message.message_type == 'comment' and message.author_id == self.env.user.partner_id:  # should use message_values to avoid a read
            for eco in self:
                for approval in eco.approval_ids.filtered(lambda app: app.template_stage_id == self.stage_id and app.status == 'none' and app.approval_template_id.approval_type == 'comment'):
                    if self.env.user in approval.approval_template_id.user_ids:
                        approval.write({
                            'status': 'comment',
                            'user_id': self.env.uid
                        })
        return message

    def _create_approvals(self):
        for eco in self:
            for approval_template in eco.stage_id.approval_template_ids:
                approval = eco.approval_ids.filtered(lambda app: app.approval_template_id == approval_template and not app.is_closed)
                if not approval:
                    self.env['mrp.eco.approval'].create({
                        'eco_id': eco.id,
                        'approval_template_id': approval_template.id,
                    })

    def _create_or_update_approval(self, status):
        for eco in self:
            for approval_template in eco.stage_id.approval_template_ids.filtered(lambda a: self.env.user in a.user_ids):
                approvals = eco.approval_ids.filtered(lambda x: x.approval_template_id == approval_template and not x.is_closed)
                none_approvals = approvals.filtered(lambda a: a.status =='none')
                confirmed_approvals = approvals - none_approvals
                if none_approvals:
                    none_approvals.write({'status': status, 'user_id': self.env.uid, 'approval_date': fields.Datetime.now()})
                    confirmed_approvals.write({'is_closed': True})
                    approval = none_approvals[:1]
                else:
                    approvals.write({'is_closed': True})
                    approval = self.env['mrp.eco.approval'].create({
                        'eco_id': eco.id,
                        'approval_template_id': approval_template.id,
                        'status': status,
                        'user_id': self.env.uid,
                        'approval_date': fields.Datetime.now(),
                    })
                eco.message_post_with_view('mrp_plm.message_approval', values={'approval': approval})

    def approve(self):
        self._create_or_update_approval(status='approved')

    def reject(self):
        self._create_or_update_approval(status='rejected')

    def conflict_resolve(self):
        self.ensure_one()
        vals = {'state': 'progress'}
        if self.current_bom_id:
            vals.update({'bom_id': self.current_bom_id.id, 'current_bom_id': False})
        self.write(vals)
        # Set previous BoM on new revision and change version of BoM.
        self.new_bom_id.write({'version': self.bom_id.version + 1, 'previous_bom_id': self.bom_id.id})
        # Remove all rebase lines.
        rebase_lines = self.bom_rebase_ids + self.previous_change_ids
        rebase_lines.unlink()
        return True

    def action_new_revision(self):
        IrAttachment = self.env['ir.attachment']
        for eco in self:
            if eco.type in ('bom', 'both'):
                eco.new_bom_id = eco.bom_id.copy(default={
                    'version': eco.bom_id.version + 1,
                    'active': False,
                    'previous_bom_id': eco.bom_id.id,
                })
                attachments = IrAttachment.search([('res_model', '=', 'mrp.bom'),
                                                   ('res_id', '=', eco.bom_id.id)])
                for attachment in attachments:
                    attachment.copy(default={'res_id':eco.new_bom_id.id})
            if eco.type in ('routing', 'both'):
                eco.new_routing_id = eco.routing_id.copy(default={
                    'version': eco.routing_id.version + 1,
                    'active': False,
                    'previous_routing_id': eco.routing_id.id
                }).id
                attachments = IrAttachment.search([('res_model', '=', 'mrp.routing'),
                                                   ('res_id', '=', eco.routing_id.id)])
                for attachment in attachments:
                    attachment.copy(default={'res_id':eco.new_routing_id.id})
            if eco.type == 'both':
                eco.new_bom_id.routing_id = eco.new_routing_id.id
                for line in eco.new_bom_id.bom_line_ids:
                    line.operation_id = eco.new_routing_id.operation_ids.filtered(lambda x: x.name == line.operation_id.name).id
            # duplicate all attachment on the product
            if eco.type in ('bom', 'both', 'product'):
                attachments = self.env['mrp.document'].search([('res_model', '=', 'product.template'), ('res_id', '=', eco.product_tmpl_id.id)])
                for attach in attachments:
                    attach.copy({'res_model': 'mrp.eco', 'res_id': eco.id})
        self.write({'state': 'progress'})

    def action_apply(self):
        self.ensure_one()
        self._check_company()
        self.mapped('new_bom_id').apply_new_version()
        self.mapped('new_routing_id').apply_new_version()
        if self.type in ('bom', 'both', 'product'):
            documents = self.env['mrp.document'].search([('res_model', '=', 'product.template'), ('res_id', '=', self.product_tmpl_id.id)])
            documents.mapped('ir_attachment_id').unlink()
            for attach in self.with_context(active_test=False).mrp_document_ids:
                product_attach = attach.copy({
                    'res_model': 'product.template',
                    'res_id': self.product_tmpl_id.id,
                })
                if not attach.active:
                    product_attach.write({
                        'name': attach.name + '(v'+str(self.product_tmpl_id.version)+')'
                    })
        if self.type in ('product', 'bom', 'both'):
            self.product_tmpl_id.version = self.product_tmpl_id.version + 1
        vals = {'state': 'done'}
        stage_id = self.env['mrp.eco.stage'].search([('final_stage', '=', True), ('type_id', '=', self.type_id.id)], limit=1).id
        if stage_id:
            vals['stage_id'] = stage_id
        self.write(vals)

    def action_see_attachments(self):
        domain = ['&', ('res_model', '=', self._name), ('res_id', '=', self.id)]
        attachment_view = self.env.ref('mrp.view_document_file_kanban_mrp')
        return {
            'name': _('Attachments'),
            'domain': domain,
            'res_model': 'mrp.document',
            'type': 'ir.actions.act_window',
            'view_id': attachment_view.id,
            'views': [(attachment_view.id, 'kanban'), (False, 'form')],
            'view_mode': 'kanban,tree,form',
            'help': _('''<p class="o_view_nocontent_smiling_face">
                        Upload files to your ECO, that will be applied to the product later
                    </p><p>
                        Use this feature to store any files, like drawings or specifications.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d, 'default_company_id': %s}" % (self._name, self.id, self.company_id.id)
        }

    def open_new_bom(self):
        self.ensure_one()
        return {
            'name': _('Eco BoM'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.bom',
            'target': 'current',
            'res_id': self.new_bom_id.id,
            'context': dict(default_product_tmpl_id=self.product_tmpl_id.id, default_product_id=self.product_tmpl_id.product_variant_id.id)}

    def open_new_routing(self):
        self.ensure_one()
        return {
            'name': _('Eco Routing'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.routing',
            'target': 'current',
            'res_id': self.new_routing_id.id}


class MrpEcoBomChange(models.Model):
    _name = 'mrp.eco.bom.change'
    _description = 'ECO BoM changes'

    eco_id = fields.Many2one('mrp.eco', 'Engineering Change', ondelete='cascade')
    eco_rebase_id = fields.Many2one('mrp.eco', 'ECO Rebase', ondelete='cascade')
    rebase_id = fields.Many2one('mrp.eco', 'Rebase', ondelete='cascade')
    change_type = fields.Selection([('add', 'Add'), ('remove', 'Remove'), ('update', 'Update')], string='Type', required=True)
    product_id = fields.Many2one('product.product', 'Product', required=True)
    old_uom_id = fields.Many2one('uom.uom', 'Previous Product UoM')
    new_uom_id = fields.Many2one('uom.uom', 'New Product UoM')
    old_product_qty = fields.Float('Previous revision quantity', default=0)
    new_product_qty = fields.Float('New revision quantity', default=0)
    old_operation_id = fields.Many2one('mrp.routing.workcenter', 'Previous Consumed in Operation')
    new_operation_id = fields.Many2one('mrp.routing.workcenter', 'New Consumed in Operation')
    upd_product_qty = fields.Float('Quantity', compute='_compute_change', store=True)
    uom_change = fields.Char('Unit of Measure', compute='_compute_change', compute_sudo=True)
    operation_change = fields.Char(compute='_compute_change', string='Consumed in Operation', compute_sudo=True)
    conflict = fields.Boolean()

    @api.depends('new_product_qty', 'old_product_qty', 'old_operation_id', 'new_operation_id', 'old_uom_id', 'new_uom_id')
    def _compute_change(self):
        for rec in self:
            rec.upd_product_qty = rec.new_product_qty - rec.old_product_qty
            rec.operation_change = rec.new_operation_id.name if rec.change_type == 'add' else rec.old_operation_id.name
            rec.uom_change = False
            if (rec.old_uom_id and rec.new_uom_id) and rec.old_uom_id != rec.new_uom_id:
                rec.uom_change = rec.old_uom_id.name + ' -> ' + rec.new_uom_id.name
            if (rec.old_operation_id != rec.new_operation_id) and rec.change_type == 'update':
                rec.operation_change = (rec.old_operation_id.name or '') + ' -> ' + (rec.new_operation_id.name or '')


class MrpEcoRoutingChange(models.Model):
    _name = 'mrp.eco.routing.change'
    _description = 'Eco Routing changes'

    eco_id = fields.Many2one('mrp.eco', 'Engineering Change', ondelete='cascade', required=True)
    change_type = fields.Selection([('add', 'Add'), ('remove', 'Remove'), ('update', 'Update')], string='Type', required=True)
    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center')
    old_time_cycle_manual = fields.Float('Old manual duration', default=0)
    new_time_cycle_manual = fields.Float('New manual duration', default=0)
    upd_time_cycle_manual = fields.Float('Manual Duration Change', compute='_compute_upd_time_cycle_manual', store=True)

    @api.depends('new_time_cycle_manual', 'old_time_cycle_manual')
    def _compute_upd_time_cycle_manual(self):
        for rec in self:
            rec.upd_time_cycle_manual = rec.new_time_cycle_manual - rec.old_time_cycle_manual


class MrpEcoTag(models.Model):
    _name = "mrp.eco.tag"
    _description = "ECO Tags"

    name = fields.Char('Tag Name', required=True)
    color = fields.Integer('Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists !"),
    ]
