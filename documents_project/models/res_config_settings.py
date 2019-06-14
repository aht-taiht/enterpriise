# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def _get_default_project_folder(self):
        folder_id = self.env.user.company_id.project_folder
        if folder_id.exists():
            return folder_id
        return False

    documents_project_settings = fields.Boolean(related='company_id.documents_project_settings', readonly=False,
                                                default=lambda self: self.env.user.company_id.documents_project_settings,
                                                string="Project")
    project_folder = fields.Many2one('documents.folder', related='company_id.project_folder', readonly=False,
                                     default=_get_default_project_folder,
                                     string="project default workspace")
    project_tags = fields.Many2many('documents.tag', 'project_tags_table',
                                    related='company_id.project_tags', readonly=False,
                                    default=lambda self: self.env.user.company_id.project_tags.ids,
                                    string="Project Tags")

    @api.onchange('project_folder')
    def on_project_folder_change(self):
        if self.project_folder != self.project_tags.mapped('folder_id'):
            self.project_tags = False
