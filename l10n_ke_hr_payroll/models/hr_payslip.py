# -*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    @api.model
    def _cron_generate_pdf(self, batch_size=False):
        is_rescheduled = super()._cron_generate_pdf(batch_size=batch_size)
        if is_rescheduled:
            return is_rescheduled

        # Generate Tax deduction cards
        for model in ['l10n_ke.tax.deduction.card.line']:
            lines = self.env[model].search([('pdf_to_generate', '=', True)])
            if lines:
                BATCH_SIZE = batch_size or 30
                lines_batch = lines[:BATCH_SIZE]
                lines_batch._generate_pdf()
                lines_batch.write({'pdf_to_generate': False})
                # if necessary, retrigger the cron to generate more pdfs
                if len(lines) > BATCH_SIZE:
                    self.env.ref('hr_payroll.ir_cron_generate_payslip_pdfs')._trigger()
                    return True
        return False
