# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _


class ResCompany(models.Model):
    _inherit = "res.company"

    documents_account_settings = fields.Boolean()
    account_folder = fields.Many2one('documents.folder', string="Accounting Workspace",
                                     default=lambda self: self.env.ref('documents.documents_finance_folder',
                                                                       raise_if_not_found=False))


class DocumentsFolderSetting(models.Model):
    _name = 'documents.account.folder.setting'
    _description = 'Journal and Folder settings'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company,
                                 ondelete='cascade')
    journal_id = fields.Many2one('account.journal', required=True)
    folder_id = fields.Many2one('documents.folder', required=True)
    tag_ids = fields.Many2many('documents.tag', string="Tags")

    _sql_constraints = [
        ('journal_unique', 'unique (journal_id)', "A setting already exists for this journal"),
    ]
