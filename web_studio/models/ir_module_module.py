# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    @api.model
    def get_studio_module(self):
        """ Returns the Studio module gathering all customizations done in
            Studio (freshly created apps and customizations of existing apps).
            Creates that module if it doesn't exist yet.
        """
        studio_module = self.search([('name', '=', 'studio_customization')])
        if not studio_module:
            studio_module = self.create({
                'name': 'studio_customization',
                'application': False,
                'category_id': self.env.ref('base.module_category_customizations_studio').id,
                'shortdesc': 'Studio customizations',
                'description': """This module has been generated by Odoo Studio.
It contains the apps created with Studio and the customizations of existing apps.""",
                'state': 'installed',
                'imported': True,
                'author': self.env.company.name,
                'icon': '/base/static/description/icon.svg',
                'license': 'OPL-1',
                'dependencies_id': [(0, 0, {'name': 'web_studio'})],
            })
        return studio_module
