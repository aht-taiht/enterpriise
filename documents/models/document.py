# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions, SUPERUSER_ID, modules
from odoo.osv import expression
from odoo.tools import crop_image, image_resize_image
from ast import literal_eval
from dateutil.relativedelta import relativedelta
import re


class Document(models.Model):
    _name = 'documents.document'
    _description = 'Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Attachment
    attachment_id = fields.Many2one('ir.attachment', auto_join=True)
    attachment_name = fields.Char('Attachment Name', related='attachment_id.name', readonly=False)
    attachment_type = fields.Selection(string='Attachment Type', related='attachment_id.type', readonly=False)
    datas = fields.Binary(related='attachment_id.datas', related_sudo=True, readonly=False)
    datas_fname = fields.Char('File Name', related='attachment_id.datas_fname', readonly=False)
    file_size = fields.Integer(related='attachment_id.file_size', store=True)
    checksum = fields.Char(related='attachment_id.checksum')
    mimetype = fields.Char(related='attachment_id.mimetype', default='application/octet-stream')
    res_model = fields.Char('Resource Model', related='attachment_id.res_model', store=True, readonly=False)
    res_id = fields.Integer('Resource ID', related='attachment_id.res_id', readonly=False)
    res_name = fields.Char('Resource Name', related='attachment_id.res_name')
    index_content = fields.Text(related='attachment_id.index_content')

    # Document
    name = fields.Char('Name', copy=True, store=True, compute='_compute_name', inverse='_inverse_name')
    active = fields.Boolean(default=True, string="Active", oldname='archived')
    thumbnail = fields.Binary(readonly=1, store=True, attachment=True, compute='_compute_thumbnail')
    url = fields.Char('Url', index=True, size=1024)
    res_model_name = fields.Char(compute='_compute_res_model_name', index=True)
    type = fields.Selection([('url', 'URL'), ('binary', 'File'), ('empty', 'Empty')],
                            string='Type', required=True, store=True, default='empty', change_default=True,
                            compute='_compute_type')
    favorited_ids = fields.Many2many('res.users', string="Favorite of")
    tag_ids = fields.Many2many('documents.tag', 'document_tag_rel', string="Tags")
    partner_id = fields.Many2one('res.partner', string="Contact", track_visibility='onchange')
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user.id, string="Owner",
                               track_visibility='onchange')
    available_rule_ids = fields.Many2many('documents.workflow.rule', compute='_compute_available_rules',
                                          string='Available Rules')
    lock_uid = fields.Many2one('res.users', string="Locked by")
    create_share_id = fields.Many2one('documents.share', help='Share used to create this document')

    # Folder
    folder_id = fields.Many2one('documents.folder',
                                ondelete="restrict",
                                track_visibility="onchange",
                                required=True,
                                index=True)
    company_id = fields.Many2one('res.company', string='Company', related='folder_id.company_id', readonly=True)
    group_ids = fields.Many2many('res.groups', string="Access Groups", readonly=True,
                                 help="This attachment will only be available for the selected user groups",
                                 related='folder_id.group_ids')

    @api.depends('attachment_id.name', 'attachment_id.datas_fname')
    def _compute_name(self):
        for record in self:
            if record.attachment_name:
                record.name = record.attachment_name
            elif record.datas_fname:
                record.name = record.datas_fname

    @api.multi
    def _inverse_name(self):
        for record in self:
            if record.attachment_id:
                record.datas_fname = record.name
                record.attachment_name = record.name

    @api.onchange('url')
    def _onchange_url(self):
        if self.url and not self.name:
            self.name = self.url.rsplit('/')[-1]

    @api.depends('datas')
    def _compute_thumbnail(self):
        for record in self:
            if record.mimetype and re.match('image.*(gif|jpeg|jpg|png)', record.mimetype):
                try:
                    record.thumbnail = crop_image(record.datas, type='center', size=(80, 80), ratio=(1, 1))
                except Exception:
                    pass
            else:
                record.thumbnail = False

    @api.depends('attachment_type', 'url')
    def _compute_type(self):
        for record in self:
            record.type = 'empty'
            if record.attachment_id:
                record.type = 'binary'
            elif record.url:
                record.type = 'url'

    def get_model_names(self, domain):
        """
        Called by the front-end to get the names of the models on which the attachments are attached.

        :param domain: the domain of the read_group on documents.
        :return: the read_group result with an additional res_model_name key.
        """
        results = self.read_group(domain, ['res_model'], ['res_model'], lazy=True)
        for result in results:
            if result.get('res_model'):
                model = self.env['ir.model'].name_search(result['res_model'], limit=1)
                if model:
                    result['res_model_name'] = model[0][1]
        return results

    @api.depends('res_model')
    def _compute_res_model_name(self):
        for record in self:
            if record.res_model:
                model = self.env['ir.model'].name_search(record.res_model, limit=1)
                if model:
                    record.res_model_name = model[0][1]

    @api.multi
    def _compute_available_rules(self):
        """
        loads the rules that can be applied to the attachment.

        """
        folder_ids = self.mapped('folder_id.id')
        rule_domain = [('domain_folder_id', 'parent_of', folder_ids)] if folder_ids else []
        rules = self.env['documents.workflow.rule'].search(rule_domain)
        for rule in rules:
            domain = []
            if rule.condition_type == 'domain':
                domain = literal_eval(rule.domain) if rule.domain else []
            else:
                if rule.criteria_partner_id:
                    domain = expression.AND([[['partner_id', '=', rule.criteria_partner_id.id]], domain])
                if rule.criteria_owner_id:
                    domain = expression.AND([[['owner_id', '=', rule.criteria_owner_id.id]], domain])
                if rule.create_model:
                    domain = expression.AND([[['type', '=', 'binary']], domain])
                if rule.criteria_tag_ids:
                    contains_list = [criteria_tag.tag_id.id for criteria_tag in rule.criteria_tag_ids if criteria_tag.operator == 'contains']
                    not_contains_list = [criteria_tag.tag_id.id for criteria_tag in rule.criteria_tag_ids if criteria_tag.operator == 'notcontains']
                    if contains_list:
                        domain = expression.AND([[['tag_ids', 'in', contains_list]], domain])
                    domain = expression.AND([[['tag_ids', 'not in', not_contains_list]], domain])

            folder_domain = [['folder_id', 'child_of', rule.domain_folder_id.id]]
            subset = expression.AND([[['id', 'in', self.ids]], domain, folder_domain])
            document_ids = self.env['documents.document'].search(subset)
            for document in document_ids:
                document.available_rule_ids = [(4, rule.id, False)]

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """
        creates a new attachment from any email sent to the alias
        and adds the values defined in the share link upload settings
        to the custom values.
        """
        subject = msg_dict.get('subject', '')
        if custom_values is None:
            custom_values = {}
        defaults = {
            'name': "Mail: " % subject,
            'active': False,
        }
        defaults.update(custom_values)

        return super(Document, self).message_new(msg_dict, defaults)

    @api.model
    def _message_post_after_hook(self, message, msg_vals, model_description=False, mail_auto_delete=True):
        """
        If the res model was an attachment and a mail, adds all the custom values of the share link
            settings to the attachments of the mail.

        """
        m2m_commands = msg_vals['attachment_ids']
        share = self.create_share_id
        if share:
            attachments = self.env['ir.attachment'].browse([x[1] for x in m2m_commands])
            for attachment in attachments:
                document = self.env['documents.document'].create({
                    'name': attachment.name,
                    'attachment_id': attachment.id,
                    'partner_id': share.partner_id.id if share.partner_id else False,
                    'tag_ids': [(6, 0, share.tag_ids.ids if share.tag_ids else [])],
                    'folder_id': share.folder_id.id if share.folder_id else False,
                })
                attachment.write({
                    'res_model': 'documents.document',
                    'res_id': document.id,
                })
                document.message_post(body=msg_vals.get('body', ''), subject=self.name)
                if share.activity_option:
                    document.documents_set_activity(settings_record=share)

        return super(Document, self)._message_post_after_hook(
            message, msg_vals, model_description=model_description, mail_auto_delete=mail_auto_delete)

    @api.multi
    def documents_set_activity(self, settings_record=None):
        """
        Generate an activity based on the fields of settings_record.

        :param settings_record: the record that contains the activity fields.
                    settings_record.activity_type_id (required)
                    settings_record.activity_summary
                    settings_record.activity_note
                    settings_record.activity_date_deadline_range
                    settings_record.activity_date_deadline_range_type
                    settings_record.activity_user_id
        """
        if settings_record and settings_record.activity_type_id:
            activity_vals = {
                'activity_type_id': settings_record.activity_type_id.id,
                'summary': settings_record.activity_summary or '',
                'note': settings_record.activity_note or '',
            }
            if settings_record.activity_date_deadline_range > 0:
                activity_vals['date_deadline'] = fields.Date.context_today(settings_record) + relativedelta(
                    **{settings_record.activity_date_deadline_range_type: settings_record.activity_date_deadline_range})

            if settings_record._fields.get('activity_user_id') and settings_record.activity_user_id:
                user = settings_record.activity_user_id
            elif settings_record._fields.get('user_id') and settings_record.user_id:
                user = settings_record.user_id
            elif settings_record._fields.get('owner_id') and settings_record.owner_id:
                user = settings_record.owner_id
            else:
                user = self.env.user
            if user:
                activity_vals['user_id'] = user.id
            self.activity_schedule(**activity_vals)

    @api.multi
    def toggle_favorited(self):
        self.ensure_one()
        self.write({'favorited_ids': [(3 if self.env.user in self[0].favorited_ids else 4, self.env.user.id)]})

    @api.multi
    def toggle_lock(self):
        """
        sets a lock user, the lock user is the user who locks a file for themselves, preventing data replacement
        and archive (therefore deletion) for any user but himself.

        Members of the group documents.group_document_manager and the superuser can unlock the file regardless.
        """
        self.ensure_one()
        if self.lock_uid:
            if self.env.user == self.lock_uid or self.env.user._is_admin() or self.user_has_groups(
                    'documents.group_document_manager'):
                self.lock_uid = False
        else:
            self.lock_uid = self.env.uid

    @api.model
    def create(self, vals):
        keys = [key for key in vals if
                self._fields[key].related and self._fields[key].related[0] == 'attachment_id']
        attachment_dict = {key: vals.pop(key) for key in keys if key in vals}
        attachment = None
        if len(attachment_dict):
            attachment_dict.setdefault('name', vals.get('name', 'unnamed'))
            attachment = self.env['ir.attachment'].create(attachment_dict)
            vals['attachment_id'] = attachment.id
        new_record = super(Document, self).create(vals)
        if attachment:
            attachment.write({'res_model': 'documents.document', 'res_id': new_record.id})
        return new_record

    @api.multi
    def write(self, vals):
        for record in self:
            if record.type == 'empty' and ('datas' in vals or 'url' in vals):
                record.activity_ids.action_feedback()
            if vals.get('datas') and not vals.get('attachment_id') and not record.attachment_id:
                attachment = self.env['ir.attachment'].create({
                    'name': vals.get('datas_fname', record.name),
                    'res_model': 'documents.document',
                    'res_id': record.id
                })
                record.attachment_id = attachment.id
        return super(Document, self).write(vals)

    def split_pdf(self, indices=None, remainder=False):
        self.ensure_one()
        if self.attachment_id:
            attachment_ids = self.attachment_id.split_pdf(indices=indices, remainder=remainder)
            for attachment in attachment_ids:
                document = self.copy()
                document.write({'attachment_id': attachment.id})
