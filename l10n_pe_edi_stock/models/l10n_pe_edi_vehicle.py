# -*- coding: utf-8 -*-

from odoo import api, models, fields
from odoo.osv import expression

ISSUING_ENTITY = [
    ('01', 'National Superintendency for the Control of Security Services, Weapons, Ammunition and Explosives for Civil Use'),
    ('02', 'General Directorate of Medicines Supplies and Drugs'),
    ('03', 'General Directorate of Environmental Health'),
    ('04', 'National Agrarian Health Service'),
    ('05', 'National Forest and Wildlife Service'),
    ('06', 'Ministry of Transport and Communications'),
    ('07', 'Ministry of Production'),
    ('08', 'Ministry of the Environment'),
    ('09', 'National Agency for Fisheries Health'),
    ('10', 'Municipality of Lima'),
    ('11', 'Ministry of Health'),
    ('12', 'Regional government'),
]

class L10nPeEdiVehicle(models.Model):
    _name = 'l10n_pe_edi.vehicle'
    _description = 'PE EDI Vehicle'
    _check_company_auto = True

    name = fields.Char(
        string='Vehicle Name',
        required=True)
    license_plate = fields.Char(
        string='License Plate',
        required=True)
    operator_id = fields.Many2one(
        comodel_name='res.partner',
        string='Operator',
        check_company=True,
        help='This value will be used by default in the picking. Define this value when the operator is '
        'always the same for the vehicle.')
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company)
    is_m1l = fields.Boolean(
        string="Is M1 or L?",
        help="Motor vehicles with less than four wheels and motor vehicles for transporting "
        "passengers with no more than 8 seats."
    )
    authorization_issuing_entity = fields.Selection(selection=ISSUING_ENTITY)
    authorization_issuing_entity_number = fields.Char(string="Authorization Issuing Entity Number")

    def name_get(self):
        # OVERRIDE
        return [(vehicle.id, "[%s] %s" % (vehicle.license_plate, vehicle.name)) for vehicle in self]

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        # OVERRIDE
        domain = domain or []
        if operator != 'ilike' or (name or '').strip():
            name_domain = ['|', ('name', 'ilike', name), ('license_plate', 'ilike', name)]
            domain = expression.AND([name_domain, domain])
        return self._search(domain, limit=limit, order=order)
