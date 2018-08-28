# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    dms_project_settings = fields.Boolean()
    project_folder = fields.Many2one('documents.folder',
                                     default=lambda self: self.env.ref('documents.documents_internal_folder',
                                                                       raise_if_not_found=False))
    project_tags = fields.Many2many('documents.tag', 'project_tags_table')
