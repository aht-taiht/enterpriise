# -*- coding: utf-8 -*-

import datetime
from lxml import etree, objectify
from dateutil.relativedelta import relativedelta
import re
import logging

import requests
import suds.client

from odoo import api, fields, models
from odoo.addons.web.controllers.main import xml2json_from_elementtree
from odoo.exceptions import UserError
from odoo.tools.translate import _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

BANXICO_DATE_FORMAT = '%Y-%m-%d'

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'

    currency_interval_unit = fields.Selection([
        ('manually', 'Manually'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly')],
        default='manually', string='Interval Unit')
    currency_next_execution_date = fields.Date(string="Next Execution Date")
    currency_provider = fields.Selection([
        ('yahoo', 'Yahoo (DISCONTINUED)'),
        ('ecb', 'European Central Bank'),
        ('fta', 'Federal Tax Administration (Switzerland)'),
        ('banxico', 'Mexican Bank'),
        ('boc', 'Bank Of Canada'),
    ], default='ecb', string='Service Provider')
    last_currency_sync_date = fields.Date(string="Last Sync Date", readonly=True)

    @api.model
    def create(self, vals):
        ''' Change the default provider depending on the company data.'''
        if vals.get('country_id') and 'currency_provider' not in vals:
            code_providers = {'CH' : 'fta', 'MX': 'banxico', 'CA' : 'boc'}
            cc = self.env['res.country'].browse(vals['country_id']).code.upper()
            if cc in code_providers:
                vals['currency_provider'] = code_providers[cc]
        return super(ResCompany, self).create(vals)

    @api.model
    def set_special_defaults_on_install(self):
        ''' At module isntallation, set the default provider depending on the company country.'''
        all_companies = self.env['res.company'].search([])
        for company in all_companies:
            if company.country_id.code == 'CH':
                # Sets FTA as the default provider for every swiss company that was already installed
                company.currency_provider = 'fta'
            elif company.country_id.code == 'MX':
                # Sets Banxico as the default provider for every mexican company that was already installed
                company.currency_provider = 'banxico'
            elif company.country_id.code == 'CA':
                # Bank of Canada
                company.currency_provider = 'boc'
            else:
                company.currency_provider = 'ecb'

    @api.multi
    def update_currency_rates(self):
        ''' This method is used to update all currencies given by the provider. Depending on the selection call _update_currency_ecb _update_currency_yahoo. '''
        res = True
        for company in self:
            if company.currency_provider == 'yahoo':
                _logger.warning("Call to the discontinued Yahoo currency rate web service.")
                raise UserError(_("The Yahoo currency rate web service has been discontinued. Please select another currency rate provider."))
            elif company.currency_provider == 'ecb':
                res = company._update_currency_ecb()
            elif company.currency_provider == 'fta':
                res = company._update_currency_fta()
            elif company.currency_provider == 'banxico':
                res = company._update_currency_banxico()
            elif company.currency_provider == 'boc':
                res = company._update_currency_boc()
            if not res:
                raise UserError(_('Unable to connect to the online exchange rate platform. The web service may be temporary down. Please try again in a moment.'))
            elif company.currency_provider:
                company.last_currency_sync_date = fields.Date.today()

    def _update_currency_fta(self):
        ''' This method is used to update the currency rates using Switzerland's
        Federal Tax Administration service provider.
        Rates are given against CHF.
        '''
        available_currencies = {}
        for currency in self.env['res.currency'].search([]):
            available_currencies[currency.name] = currency

        # make sure that the CHF is enabled
        if not available_currencies.get('CHF'):
            chf_currency = self.env['res.currency'].with_context(active_test=False).search([('name', '=', 'CHF')])
            if chf_currency:
                chf_currency.write({'active': True})
            else:
                chf_currency = self.env['res.currency'].create({'name': 'CHF'})
            available_currencies['CHF'] = chf_currency

        request_url = 'http://www.afd.admin.ch/publicdb/newdb/mwst_kurse/wechselkurse.php'
        try:
            parse_url = requests.request('GET', request_url)
        except:
            return False

        xml_tree = etree.fromstring(parse_url.content)
        rates_dict = self._parse_fta_data(xml_tree, available_currencies)

        for company in self:
            base_currency = company.currency_id.name
            base_currency_rate = rates_dict.get(base_currency)
            if not base_currency_rate:
                raise UserError(_("Your main currency %s is unsupported by this exchange rate provider. Please choose another one.") % base_currency)

            for currency, rate in rates_dict.items():
                company_rate = rate / base_currency_rate
                self.env['res.currency.rate'].create({'currency_id':available_currencies[currency].id, 'rate':company_rate, 'name':fields.Date.today(), 'company_id':company.id})

        return True

    def _parse_fta_data(self, xml_tree, available_currencies):
        ''' Parses the data returned in xml by FTA servers and returns it in a more
        Python-usable form.'''
        rates_dict = {}
        rates_dict['CHF'] = 1.0
        data = xml2json_from_elementtree(xml_tree)

        for child_node in data['children']:
            if child_node['tag'] == 'devise':
                currency_code = child_node['attrs']['code'].upper()

                if currency_code in available_currencies:
                    currency_xml = None
                    rate_xml = None

                    for sub_child in child_node['children']:
                        if sub_child['tag'] == 'waehrung':
                            currency_xml = sub_child['children'][0]
                        elif sub_child['tag'] == 'kurs':
                            rate_xml = sub_child['children'][0]
                        if currency_xml and rate_xml:
                            #avoid iterating for nothing on children
                            break

                    rates_dict[currency_code] = float(re.search('\d+',currency_xml).group()) / float(rate_xml)
        return rates_dict

    def _update_currency_ecb(self):
        ''' This method is used to update the currencies by using ECB service provider.
            Rates are given against EURO
        '''
        Currency = self.env['res.currency']
        CurrencyRate = self.env['res.currency.rate']

        currencies = Currency.search([])
        currencies = [x.name for x in currencies]
        request_url = "http://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
        try:
            parse_url = requests.request('GET', request_url)
        except:
            #connection error, the request wasn't successful
            return False
        xmlstr = etree.fromstring(parse_url.content)
        data = xml2json_from_elementtree(xmlstr)
        node = data['children'][2]['children'][0]
        currency_node = [(x['attrs']['currency'], x['attrs']['rate']) for x in node['children'] if x['attrs']['currency'] in currencies]
        for company in self:
            base_currency_rate = 1
            if company.currency_id.name != 'EUR':
                #find today's rate for the base currency
                base_currency = company.currency_id.name
                base_currency_rates = [(x['attrs']['currency'], x['attrs']['rate']) for x in node['children'] if x['attrs']['currency'] == base_currency]
                base_currency_rate = len(base_currency_rates) and base_currency_rates[0][1] or 1
                currency_node += [('EUR', '1.0000')]

            for currency_code, rate in currency_node:
                rate = float(rate) / float(base_currency_rate)
                currency = Currency.search([('name', '=', currency_code)], limit=1)
                if currency:
                    CurrencyRate.create({'currency_id': currency.id, 'rate': rate, 'name': fields.Date.today(), 'company_id': company.id})
        return True

    def _update_currency_boc(self):
        """This method is used to update currencies exchange rate by using Bank
           Of Canada daily exchange rate service.
           Exchange rates are expressed as 1 unit of the foreign currency converted into Canadian dollars.
           Keys are in this format: 'FX{CODE}CAD' e.g.: 'FXEURCAD'
        """
        Currency = self.env['res.currency']
        CurrencyRate = self.env['res.currency.rate']

        available_currencies = {}
        for currency in self.env['res.currency'].search([]):
            available_currencies[currency.name] = currency

        request_url = "http://www.bankofcanada.ca/valet/observations/group/FX_RATES_DAILY/json"
        try:
            response = requests.request('GET', request_url)
        except:
            #connection error, the request wasn't successful
            return False
        if not 'application/json' in response.headers.get('Content-Type', ''):
            return False
        data = response.json()
        # 'observations' key contains rates observations by date
        last_observation_date = sorted([obs['d'] for obs in data['observations']])[-1]
        last_obs = [obs for obs in data['observations'] if obs['d'] == last_observation_date][0]
        last_obs.update({'FXCADCAD': {'v': '1'}})
        for company in self:
            base_currency_rate = 1
            if company.currency_id.name != 'CAD':
                comp_obs = last_obs.get('FX{}CAD'.format(company.currency_id.name), None)
                if comp_obs is not None:
                    base_currency_rate = float(comp_obs['v'])
            for curency_name in available_currencies.keys():
                curency_obs = last_obs.get('FX{}CAD'.format(curency_name), None)
                if curency_obs is not None:
                    rate = float(base_currency_rate) / float(curency_obs['v'])
                    CurrencyRate.create({'currency_id': available_currencies[curency_name].id, 'rate': rate, 'name': fields.Date.today(), 'company_id': company.id})
            # Just in case a company is in CAD and CAD is not activated
            if company.currency_id.rate != 1.0 and company.currency_id.name == 'CAD' and 'CAD' not in available_currencies.keys():
                CurrencyRate.create({'currency_id': company.currency_id.id, 'rate': 1.0, 'name': fields.Date.today(), 'company_id': company.id})
        return True

    def _update_currency_banxico(self):
        """Update the USD exchange against the MXN forcing using Banxico.
        * With basement in legal topics in Mexico the rate must be **one** per day and it is equal to the rate known the
        day immediate before the rate is gotten, it means the rate for 02/Feb is the one at 31/jan.
        * The base currency is always MXN but with the inverse 1/rate.
        * The official institution is Banxico.
        * The webservice returns the following currency rates (same order):
            1) USD SAT - Officially used from SAT institution
            2) USD Fixed
            3) EUR
            4) CAD
            5) JPY
            6) GAB
        Source: http://www.banxico.org.mx/portal-mercado-cambiario/
        """
        def update_rate(currency, rate, date):
            #  Deleting current rate values because we can only have one
            currency.rate_ids.filtered(lambda r: date == r.name).unlink()
            self.env['res.currency.rate'].create({
                'rate': rate,
                'currency_id': currency.id,
                'name': date,
                'company_id': self.id,
            })
            # Update cached rate field
            currency._compute_current_rate()
        try:
            client = suds.client.Client('http://www.banxico.org.mx/DgieWSWeb/DgieWS?WSDL', cache=None)
            xml_str = client.service.tiposDeCambioBanxico().encode('utf-8')
        except:
            return False
        xml = objectify.fromstring(xml_str)
        ns = xml.nsmap
        # nsmap don't support "None" key then deleting
        ns.pop(None, None)
        serie = xml.xpath("bm:DataSet/bm:Series[1]/bm:Obs", namespaces=ns)[0]
        usd_mxn = float(serie.get('OBS_VALUE'))
        date = datetime.datetime.strptime(
            serie.get('TIME_PERIOD'), BANXICO_DATE_FORMAT).strftime(DEFAULT_SERVER_DATE_FORMAT)
        mxn = self.env.ref('base.MXN')
        usd = self.env.ref('base.USD')
        base_currency = mxn
        currency_to_update = usd
        rate = 1.0 / usd_mxn
        if mxn.rate != 1.0 and usd.rate == 1.0:
            # Most of the time Mexico use USD.rate=1 and company.currency=MXN
            base_currency = usd
            currency_to_update = mxn
            rate = usd_mxn
        else:
            # Force MXN.rate=1 to get a valid base
            update_rate(mxn, 1.0, date)
        update_rate(currency_to_update, rate, date)
        base_mxn_rate = base_currency._convert(1.0, mxn, self, date, round=False)
        foreigns = {
            # position order of the rates from webservices
            3: self.env.ref('base.EUR'),
            4: self.env.ref('base.CAD'),
            5: self.env.ref('base.JPY'),
            6: self.env.ref('base.GBP'),
        }
        for index, currency in foreigns.items():
            serie = xml.xpath("bm:DataSet/bm:Series[%d]/bm:Obs" % index, namespaces=ns)[0]
            try:
                foreign_mxn_rate = float(serie.get('OBS_VALUE'))
            except ValueError:
                continue
            foreign_rate_date = datetime.datetime.strptime(
                serie.get('TIME_PERIOD'), BANXICO_DATE_FORMAT).strftime(DEFAULT_SERVER_DATE_FORMAT)
            update_rate(currency, base_mxn_rate / foreign_mxn_rate, foreign_rate_date)
        return True

    @api.model
    def run_update_currency(self):
        ''' This method is called from a cron job. Depending on the selection call _update_currency_ecb _update_currency_yahoo. '''
        records = self.search([('currency_next_execution_date', '<=', fields.Date.today())])
        if records:
            to_update = self.env['res.company']
            for record in records:
                if record.currency_interval_unit == 'daily':
                    next_update = relativedelta(days=+1)
                elif record.currency_interval_unit == 'weekly':
                    next_update = relativedelta(weeks=+1)
                elif record.currency_interval_unit == 'monthly':
                    next_update = relativedelta(months=+1)
                else:
                    record.currency_next_execution_date = False
                    continue
                record.currency_next_execution_date = datetime.datetime.now() + next_update
                to_update += record
            to_update.update_currency_rates()


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    currency_interval_unit = fields.Selection(related="company_id.currency_interval_unit",)
    currency_provider = fields.Selection(related="company_id.currency_provider")
    currency_next_execution_date = fields.Date(related="company_id.currency_next_execution_date")
    last_currency_sync_date = fields.Date(related="company_id.last_currency_sync_date")

    @api.onchange('currency_interval_unit')
    def onchange_currency_interval_unit(self):
        #as the onchange is called upon each opening of the settings, we avoid overwriting
        #the next execution date if it has been already set
        if self.company_id.currency_next_execution_date:
            return
        if self.currency_interval_unit == 'daily':
            next_update = relativedelta(days=+1)
        elif self.currency_interval_unit == 'weekly':
            next_update = relativedelta(weeks=+1)
        elif self.currency_interval_unit == 'monthly':
            next_update = relativedelta(months=+1)
        else:
            self.currency_next_execution_date = False
            return
        self.currency_next_execution_date = datetime.date.today() + next_update

    @api.multi
    def update_currency_rates(self):
        companies = self.env['res.company'].browse([record.company_id.id for record in self])
        companies.update_currency_rates()
