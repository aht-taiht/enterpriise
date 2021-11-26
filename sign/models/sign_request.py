# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io
import os
import time
import uuid

from PyPDF2 import PdfFileReader, PdfFileWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.rl_config import TTFSearchPath
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase.pdfmetrics import stringWidth
from werkzeug.urls import url_join, url_quote
from random import randint
from markupsafe import Markup

from odoo import api, fields, models, http, _, Command
from odoo.tools import config, get_lang, is_html_empty, formataddr
from odoo.exceptions import UserError, ValidationError

TTFSearchPath.append(os.path.join(config["root_path"], "..", "addons", "web", "static", "fonts", "sign"))


def _fix_image_transparency(image):
    """ Modify image transparency to minimize issue of grey bar artefact.

    When an image has a transparent pixel zone next to white pixel zone on a
    white background, this may cause on some renderer grey line artefacts at
    the edge between white and transparent.

    This method sets transparent pixel to white transparent pixel which solves
    the issue for the most probable case. With this the issue happen for a
    black zone on black background but this is less likely to happen.
    """
    pixels = image.load()
    for x in range(image.size[0]):
        for y in range(image.size[1]):
            if pixels[x, y] == (0, 0, 0, 0):
                pixels[x, y] = (255, 255, 255, 0)

class SignRequest(models.Model):
    _name = "sign.request"
    _description = "Signature Request"
    _rec_name = 'reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _default_access_token(self):
        return str(uuid.uuid4())

    def _expand_states(self, states, domain, order):
        return [key for key, val in type(self).state.selection]

    def _get_mail_link(self, email, subject):
        return "mailto:%s?subject=%s" % (url_quote(email), url_quote(subject))

    template_id = fields.Many2one('sign.template', string="Template", required=True)
    subject = fields.Char(string="Email Subject")
    reference = fields.Char(required=True, string="Document Name", help="This is how the document will be named in the mail")

    access_token = fields.Char('Security Token', required=True, default=_default_access_token, readonly=True)

    request_item_ids = fields.One2many('sign.request.item', 'sign_request_id', string="Signers")
    refusal_allowed = fields.Boolean(default=False, string="Can be refused", help="Allow the contacts to refuse the document for a specific reason.")
    state = fields.Selection([
        ("sent", "Sent"),
        ("signed", "Fully Signed"),
        ("refused", "Refused"),
        ("canceled", "Canceled")
    ], default='sent', tracking=True, group_expand='_expand_states')

    completed_document = fields.Binary(readonly=True, string="Completed Document", attachment=True)

    nb_wait = fields.Integer(string="Sent Requests", compute="_compute_count", store=True)
    nb_closed = fields.Integer(string="Completed Signatures", compute="_compute_count", store=True)
    nb_total = fields.Integer(string="Requested Signatures", compute="_compute_count", store=True)
    progress = fields.Char(string="Progress", compute="_compute_count", compute_sudo=True)
    start_sign = fields.Boolean(string="Signature Started", help="At least one signer has signed the document.", compute="_compute_count", compute_sudo=True)
    integrity = fields.Boolean(string="Integrity of the Sign request", compute='_compute_hashes', compute_sudo=True)

    active = fields.Boolean(default=True, string="Active")
    favorited_ids = fields.Many2many('res.users', string="Favorite of")

    color = fields.Integer()
    request_item_infos = fields.Binary(compute="_compute_request_item_infos")
    last_action_date = fields.Datetime(related="message_ids.create_date", readonly=True, string="Last Action Date")
    completion_date = fields.Date(string="Completion Date", compute="_compute_count", compute_sudo=True)

    sign_log_ids = fields.One2many('sign.log', 'sign_request_id', string="Logs", help="Activity logs linked to this request")
    template_tags = fields.Many2many('sign.template.tag', string='Template Tags', related='template_id.tag_ids')
    cc_partner_ids = fields.Many2many('res.partner', string='Copy to')
    message = fields.Html('sign.message')
    message_cc = fields.Html('sign.message_cc')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments', readonly=True, ondelete="restrict")

    need_my_signature = fields.Boolean(compute='_compute_need_my_signature', search='_search_need_my_signature')

    def _compute_need_my_signature(self):
        my_partner_id = self.env.user.partner_id
        for sign_request in self:
            sign_request.need_my_signature = any(sri.partner_id.id == my_partner_id.id and sri.state == 'sent' for sri in sign_request.request_item_ids)

    @api.model
    def _search_need_my_signature(self, operator, value):
        my_partner_id = self.env.user.partner_id
        if operator not in ['=', '!='] or not isinstance(value, bool):
            return []
        domain_operator = 'not in' if (operator == '=') ^ value else 'in'
        documents_ids = self.env['sign.request.item'].search([('partner_id.id', '=', my_partner_id.id), ('state', '=', 'sent')]).mapped('sign_request_id').ids
        return [('id', domain_operator, documents_ids)]

    @api.depends('request_item_ids.state')
    def _compute_count(self):
        for rec in self:
            wait, closed = 0, 0
            for s in rec.request_item_ids:
                if s.state == "sent":
                    wait += 1
                if s.state in ["completed", "refused", "canceled"]:
                    closed += 1
            rec.nb_wait = wait
            rec.nb_closed = closed
            rec.nb_total = wait + closed
            rec.start_sign = bool(closed)
            rec.progress = "{} / {}".format(closed, wait + closed)
            if closed:
                rec.start_sign = True
            signed_requests = rec.request_item_ids.filtered('signing_date')
            if wait == 0 and closed and signed_requests:
                last_completed_request = signed_requests.sorted(key=lambda i: i.signing_date, reverse=True)[0]
                rec.completion_date = last_completed_request.signing_date
            else:
                rec.completion_date = None

    @api.depends('request_item_ids.state', 'request_item_ids.partner_id.name')
    def _compute_request_item_infos(self):
        for request in self:
            request.request_item_infos = [{
                'id': item.id,
                'partner_name': item.partner_id.sudo().name or _('Public User'),
                'state': item.state,
                'signing_date': item.signing_date or ''
            } for item in request.request_item_ids]

    @api.model_create_multi
    def create(self, vals_list):
        sign_requests = super().create(vals_list)
        sign_requests.template_id.check_send_ready()
        sign_requests.cc_partner_ids = [Command.link(self.env.user.partner_id.id)]
        for sign_request in sign_requests:
            if not sign_request.request_item_ids:
                raise ValidationError(_("A valid sign request needs at least one sign request item"))
            sign_request.attachment_ids.write({'res_model': sign_request._name, 'res_id': sign_request.id})
            sign_request.message_subscribe(partner_ids=sign_request.cc_partner_ids.ids + sign_request.request_item_ids.partner_id.ids)
            sign_users = sign_request.request_item_ids.partner_id.user_ids.filtered(lambda u: u.has_group('sign.group_sign_employee'))
            sign_request.activity_update(sign_users)
            self.env['sign.log']._create_log(sign_request, "create", is_request=True)
        if not self._context.get('no_sign_mail'):
            sign_requests.send_signature_accesses()
        return sign_requests

    def toggle_active(self):
        self.filtered(lambda sr: sr.active and sr.state == 'sent').cancel()
        super(SignRequest, self).toggle_active()

    def _check_senders_validity(self):
        invalid_senders = self.create_uid.filtered(lambda u: not u.email_formatted)
        if invalid_senders:
            raise ValidationError(_("Please configure senders'(%s) email addresses", ', '.join(invalid_senders.mapped('name'))))

    def _check_after_compute(self):
        for rec in self:
            if rec.state == 'sent' and rec.nb_closed == len(rec.request_item_ids) and len(rec.request_item_ids) > 0: # All signed
                rec.action_signed()

    def _get_final_recipients(self):
        all_recipients = set(self.request_item_ids.mapped('signer_email')) | \
                         set(self.cc_partner_ids.filtered(lambda p: p.email_formatted).mapped('email'))
        return all_recipients

    def go_to_document(self):
        self.ensure_one()
        request_item = self.request_item_ids.filtered(lambda r: r.partner_id and r.partner_id.id == self.env.user.partner_id.id)[:1]
        return {
            'name': self.reference,
            'type': 'ir.actions.client',
            'tag': 'sign.Document',
            'context': {
                'id': self.id,
                'token': self.access_token,
                'sign_token': request_item.access_token if request_item and request_item.state == "sent" else None,
                'create_uid': self.create_uid.id,
                'state': self.state,
                'request_item_states': {str(item.id): item.is_mail_sent for item in self.request_item_ids},
            },
        }

    def go_to_signable_document(self):
        self.ensure_one()
        request_item = self.request_item_ids.filtered(lambda r: r.partner_id and r.partner_id.id == self.env.user.partner_id.id)[:1]
        return {
            'name': self.reference,
            'type': 'ir.actions.client',
            'tag': 'sign.SignableDocument',
            'context': {
                'id': self.id,
                'token': request_item.access_token if request_item and request_item.state == "sent" else None,
                'sign_token': request_item.access_token if request_item and request_item.state == "sent" else None,
                'create_uid': self.create_uid.id,
                'state': self.state,
                'request_item_states': dict((item.id, item.is_mail_sent) for item in self.request_item_ids),
            },
        }

    def open_request(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sign.request",
            "views": [[False, "form"]],
            "res_id": self.id,
        }

    def open_template(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Templates"),
            "res_model": "sign.template",
            "domain": [["id", "=", self.template_id.id], ["active", "=", self.template_id.active]],
            "views": [[False, 'kanban']]
        }

    def get_completed_document(self):
        self.ensure_one()
        if not self.completed_document:
            self.generate_completed_document()

        return {
            'name': 'Signed Document',
            'type': 'ir.actions.act_url',
            'url': '/sign/download/%(request_id)s/%(access_token)s/completed' % {'request_id': self.id, 'access_token': self.access_token},
        }

    def open_logs(self):
        self.ensure_one()
        return {
            "name": _("Activity Logs"),
            "type": "ir.actions.act_window",
            "res_model": "sign.log",
            'view_mode': 'tree,form',
            'domain': [('sign_request_id', '=', self.id)],
        }

    @api.onchange("progress", "start_sign")
    def _compute_hashes(self):
        for document in self:
            try:
                document.integrity = self.sign_log_ids._check_document_integrity()
            except Exception:
                document.integrity = False

    def toggle_favorited(self):
        self.ensure_one()
        self.write({'favorited_ids': [(3 if self.env.user in self.favorited_ids else 4, self.env.user.id)]})

    def _refuse(self, refuser, refusal_reason):
        self.ensure_one()
        if self.state != 'sent' or not self.refusal_allowed:
            raise UserError(_("This sign request cannot be refused"))
        self._check_senders_validity()
        self.write({'state': 'refused'})
        self.request_item_ids._cancel(no_access=False)

        # cancel request and activities for other unsigned users
        for user in self.request_item_ids.partner_id.user_ids.filtered(lambda u: u.has_group('sign.group_sign_employee')):
            self.activity_unlink(['mail.mail_activity_data_todo'], user_id=user.id)

        # send emails to signers and cc_partners
        for sign_request_item in self.request_item_ids:
            self._send_refused_mail(refuser, refusal_reason, sign_request_item.partner_id, access_token=sign_request_item.access_token, force_send=True)
        for partner in self.cc_partner_ids.filtered(lambda p: p.email_formatted) - self.request_item_ids.partner_id:
            self._send_refused_mail(refuser, refusal_reason, partner)

    def _send_refused_mail(self, refuser, refusal_reason, partner, access_token=None, force_send=False):
        self.ensure_one()
        if access_token is None:
            access_token = self.access_token
        subject = _("The document (%s) has been rejected by one of the signers", self.template_id.name)
        base_url = self.get_base_url()
        partner_lang = get_lang(self.env, lang_code=partner.lang).code
        tpl = self.env.ref('sign.sign_template_mail_refused')
        body = tpl.with_context(lang=partner_lang)._render({
            'record': self,
            'recipient': partner,
            'refuser': refuser,
            'link': url_join(base_url, 'sign/document/%s/%s' % (self.id, access_token)),
            'subject': subject,
            'body': Markup('<p style="white-space: pre">{}</p>').format(refusal_reason),
        }, engine='ir.qweb', minimal_qcontext=True)

        self._message_send_mail(
            body, 'mail.mail_notification_light',
            {'record_name': self.reference},
            {'model_description': 'signature', 'company': self.create_uid.company_id},
            {'email_from': self.create_uid.email_formatted,
             'author_id': self.create_uid.partner_id.id,
             'email_to': formataddr((partner.name, partner.email_formatted)),
             'subject': subject},
            force_send=force_send,
            lang=partner_lang,
        )

    def send_signature_accesses(self):
        # Send/Resend accesses for 'sent' sign.request.items by email
        self._check_senders_validity()
        for sign_request in self:
            request_items = sign_request.request_item_ids.filtered(lambda sri: sri.state == 'sent')
            if request_items:
                request_items._send_signature_access_mail()
                body = _("The signature mail is sent to: ")
                receiver_names = ["%s(%s)" % (sri.partner_id.name, sri.role_id.name) for sri in request_items]
                body += ', '.join(receiver_names)
                if not is_html_empty(sign_request.message):
                    body += sign_request.message
                sign_request.message_post(body=body, attachment_ids=sign_request.attachment_ids.ids)

    def action_signed(self):
        self.write({'state': 'signed'})
        self.env.cr.commit()
        if not self.check_is_encrypted():
            # if the file is encrypted, we must wait that the document is decrypted
            self.send_completed_document()

    def check_is_encrypted(self):
        self.ensure_one()
        if not self.template_id.sign_item_ids:
            return False

        old_pdf = PdfFileReader(io.BytesIO(base64.b64decode(self.template_id.attachment_id.datas)), strict=False, overwriteWarnings=False)
        return old_pdf.isEncrypted

    def cancel(self):
        for sign_request in self:
            sign_request.write({'access_token': self._default_access_token(), 'state': 'canceled'})
        self.request_item_ids._cancel()

        # cancel activities for signers
        for user in self.request_item_ids.partner_id.user_ids.filtered(lambda u: u.has_group('sign.group_sign_employee')):
            self.activity_unlink(['mail.mail_activity_data_todo'], user_id=user.id)

        for sign_request in self:
            self.env['sign.log']._create_log(sign_request, 'cancel', is_request=True)

    @api.model
    def check_request_edit_during_sign(self, request_id):
        request_sudo = self.sudo().browse(request_id)
        return request_sudo.exists() and request_sudo.nb_closed == 0 and self.env.user.has_group('base.group_user')

    def send_completed_document(self):
        self.ensure_one()
        if self.state != 'signed':
            raise UserError(_('The sign request has not been fully signed'))
        self._check_senders_validity()

        if not self.completed_document:
            self.generate_completed_document()

        attachment = self.env['ir.attachment'].create({
            'name': "%s.pdf" % self.reference if self.reference.split('.')[-1] != 'pdf' else self.reference,
            'datas': self.completed_document,
            'type': 'binary',
            'res_model': self._name,
            'res_id': self.id,
        })
        report_action = self.env.ref('sign.action_sign_request_print_logs')
        # print the report with the public user in a sudoed env
        # public user because we don't want groups to pollute the result
        # (e.g. if the current user has the group Sign Manager,
        # some private information will be sent to *all* signers)
        # sudoed env because we have checked access higher up the stack
        public_user = self.env.ref('base.public_user', raise_if_not_found=False)
        if not public_user:
            # public user was deleted, fallback to avoid crash (info may leak)
            public_user = self.env.user
        pdf_content, __ = report_action.with_user(public_user).sudo()._render_qweb_pdf(self.id)
        attachment_log = self.env['ir.attachment'].create({
            'name': "Certificate of completion - %s.pdf" % time.strftime('%Y-%m-%d - %H:%M:%S'),
            'raw': pdf_content,
            'type': 'binary',
            'res_model': self._name,
            'res_id': self.id,
        })
        signers = [{'name': signer.partner_id.name, 'email': signer.signer_email, 'id': signer.partner_id.id} for signer in self.request_item_ids]
        self.attachment_ids = [Command.link(attachment.id), Command.link(attachment_log.id)]
        request_edited = any(log.action == "update" for log in self.sign_log_ids)
        for sign_request_item in self.request_item_ids:
            self._send_completed_document_mail(signers, request_edited, sign_request_item.partner_id, access_token=sign_request_item.access_token, with_message_cc=sign_request_item.partner_id in self.cc_partner_ids, force_send=True)

        cc_partners_valid = self.cc_partner_ids.filtered(lambda p: p.email_formatted)
        for cc_partner in cc_partners_valid - self.request_item_ids.partner_id:
            self._send_completed_document_mail(signers, request_edited, cc_partner)
        if cc_partners_valid:
            body = _("The CC mail is sent to: ") + ', '.join(cc_partners_valid.mapped('name'))
            if not is_html_empty(self.message_cc):
                body += self.message_cc
            self.message_post(body=body, attachment_ids=self.attachment_ids.ids)

    def _send_completed_document_mail(self, signers, request_edited, partner, access_token=None, with_message_cc=True, force_send=False):
        self.ensure_one()
        if access_token is None:
            access_token = self.access_token
        tpl = self.env.ref('sign.sign_template_mail_completed')
        partner_lang = get_lang(self.env, lang_code=partner.lang).code
        tpl = tpl.with_context(lang=partner_lang)
        base_url = self.get_base_url()
        body = tpl._render({
            'record': self,
            'link': url_join(base_url, 'sign/document/%s/%s' % (self.id, access_token)),
            'subject': '%s signed' % self.reference,
            'body': self.message_cc if with_message_cc and not is_html_empty(self.message_cc) else False,
            'recipient_name': partner.name,
            'recipient_id': partner.id,
            'signers': signers,
            'request_edited': request_edited,
        }, engine='ir.qweb', minimal_qcontext=True)

        self.env['sign.request']._message_send_mail(
            body, 'mail.mail_notification_light',
            {'record_name': self.reference},
            {'model_description': 'signature', 'company': self.create_uid.company_id},
            {'email_from': self.create_uid.email_formatted,
             'author_id': self.create_uid.partner_id.id,
             'email_to': partner.email_formatted,
             'subject': _('%s has been edited and signed', self.reference) if request_edited else _('%s has been signed', self.reference),
             'attachment_ids': self.attachment_ids.ids},
            force_send=force_send,
            lang=partner_lang,
        )

    def _get_font(self):
        custom_font = self.env["ir.config_parameter"].sudo().get_param("sign.use_custom_font")
        # The font must be a TTF font. The tool 'otf2ttf' may be useful for conversion.
        if custom_font:
            pdfmetrics.registerFont(TTFont(custom_font, custom_font + ".ttf"))
            return custom_font
        return "Helvetica"

    def _get_normal_font_size(self):
        return 0.015

    def generate_completed_document(self, password=""):
        self.ensure_one()
        if not self.template_id.sign_item_ids:
            self.completed_document = self.template_id.attachment_id.datas
            return

        try:
            old_pdf = PdfFileReader(io.BytesIO(base64.b64decode(self.template_id.attachment_id.datas)), strict=False, overwriteWarnings=False)
            old_pdf.getNumPages()
        except:
            raise ValidationError(_("ERROR: Invalid PDF file!"))

        isEncrypted = old_pdf.isEncrypted
        if isEncrypted and not old_pdf.decrypt(password):
            # password is not correct
            return

        font = self._get_font()
        normalFontSize = self._get_normal_font_size()

        packet = io.BytesIO()
        can = canvas.Canvas(packet)
        itemsByPage = self.template_id.sign_item_ids.getByPage()
        SignItemValue = self.env['sign.request.item.value']
        for p in range(0, old_pdf.getNumPages()):
            page = old_pdf.getPage(p)
            # Absolute values are taken as it depends on the MediaBox template PDF metadata, they may be negative
            width = float(abs(page.mediaBox.getWidth()))
            height = float(abs(page.mediaBox.getHeight()))

            # Set page orientation (either 0, 90, 180 or 270)
            rotation = page['/Rotate'] if '/Rotate' in page else 0
            if rotation and isinstance(rotation, int):
                can.rotate(rotation)
                # Translate system so that elements are placed correctly
                # despite of the orientation
                if rotation == 90:
                    width, height = height, width
                    can.translate(0, -height)
                elif rotation == 180:
                    can.translate(-width, -height)
                elif rotation == 270:
                    width, height = height, width
                    can.translate(-width, 0)

            items = itemsByPage[p + 1] if p + 1 in itemsByPage else []
            for item in items:
                value = SignItemValue.search([('sign_item_id', '=', item.id), ('sign_request_id', '=', self.id)], limit=1)
                if not value or not value.value:
                    continue

                value = value.value

                if item.type_id.item_type == "text":
                    can.setFont(font, height*item.height*0.8)
                    if item.alignment == "left":
                        can.drawString(width*item.posX, height*(1-item.posY-item.height*0.9), value)
                    elif item.alignment == "right":
                        can.drawRightString(width*(item.posX+item.width), height*(1-item.posY-item.height*0.9), value)
                    else:
                        can.drawCentredString(width*(item.posX+item.width/2), height*(1-item.posY-item.height*0.9), value)

                elif item.type_id.item_type == "selection":
                    content = []
                    for option in item.option_ids:
                        if option.id != int(value):
                            content.append("<strike>%s</strike>" % (option.value))
                        else:
                            content.append(option.value)
                    font_size = height * normalFontSize * 0.8
                    can.setFont(font, font_size)
                    text = " / ".join(content)
                    string_width = stringWidth(text.replace("<strike>", "").replace("</strike>", ""), font, font_size)
                    p = Paragraph(text, getSampleStyleSheet()["Normal"])
                    w, h = p.wrap(width, height)
                    posX = width * (item.posX + item.width * 0.5) - string_width // 2
                    posY = height * (1 - item.posY - item.height * 0.5) - h // 2
                    p.drawOn(can, posX, posY)

                elif item.type_id.item_type == "textarea":
                    can.setFont(font, height*normalFontSize*0.8)
                    lines = value.split('\n')
                    y = (1-item.posY)
                    for line in lines:
                        y -= normalFontSize*0.9
                        can.drawString(width*item.posX, height*y, line)
                        y -= normalFontSize*0.1

                elif item.type_id.item_type == "checkbox":
                    can.setFont(font, height*item.height*0.8)
                    value = 'X' if value == 'on' else ''
                    can.drawString(width*item.posX, height*(1-item.posY-item.height*0.9), value)

                elif item.type_id.item_type == "signature" or item.type_id.item_type == "initial":
                    image_reader = ImageReader(io.BytesIO(base64.b64decode(value[value.find(',')+1:])))
                    _fix_image_transparency(image_reader._image)
                    can.drawImage(image_reader, width*item.posX, height*(1-item.posY-item.height), width*item.width, height*item.height, 'auto', True)

            can.showPage()

        can.save()

        item_pdf = PdfFileReader(packet, overwriteWarnings=False)
        new_pdf = PdfFileWriter()

        for p in range(0, old_pdf.getNumPages()):
            page = old_pdf.getPage(p)
            page.mergePage(item_pdf.getPage(p))
            new_pdf.addPage(page)

        if isEncrypted:
            new_pdf.encrypt(password)

        output = io.BytesIO()
        new_pdf.write(output)
        self.completed_document = base64.b64encode(output.getvalue())
        output.close()

    @api.model
    def _message_send_mail(self, body, email_layout_xmlid, message_values, notif_values, mail_values, force_send=False, **kwargs):
        """ Shortcut to send an email. """
        default_lang = get_lang(self.env, lang_code=kwargs.get('lang')).code
        lang = kwargs.get('lang', default_lang)
        sign_request = self.with_context(lang=lang)

        # the notif layout wrapping expects a mail.message record, but we don't want
        # to actually create the record
        # See @tde-banana-odoo for details
        msg = sign_request.env['mail.message'].sudo().new(dict(body=body, **message_values))
        email_layout = sign_request.env.ref(email_layout_xmlid)
        body_html = email_layout._render(dict(message=msg, **notif_values), engine='ir.qweb', minimal_qcontext=True)
        body_html = sign_request.env['mail.render.mixin']._replace_local_links(body_html)

        mail = sign_request.env['mail.mail'].sudo().create(dict(body_html=body_html, **mail_values))
        if force_send:
            mail.send()
        return mail

    @api.model
    def activity_update(self, sign_users):
        for user in sign_users:
            self.with_context(mail_activity_quick_update=True).activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id
            )


class SignRequestItem(models.Model):
    _name = "sign.request.item"
    _description = "Signature Request Item"
    _inherit = ['portal.mixin']
    _rec_name = 'partner_id'

    def _default_access_token(self):
        return str(uuid.uuid4())

    def _get_mail_link(self, email, subject):
        return "mailto:%s?subject=%s" % (url_quote(email), url_quote(subject))

    partner_id = fields.Many2one('res.partner', string="Signer", ondelete='restrict')
    sign_request_id = fields.Many2one('sign.request', string="Signature Request", ondelete='cascade', required=True)
    sign_item_value_ids = fields.One2many('sign.request.item.value', 'sign_request_item_id', string="Value")
    reference = fields.Char(related='sign_request_id.reference', string="Document Name")

    access_token = fields.Char(required=True, default=_default_access_token, readonly=True)
    access_via_link = fields.Boolean('Accessed Through Token')
    role_id = fields.Many2one('sign.item.role', string="Role", required=True, readonly=True)
    sms_number = fields.Char(related='partner_id.mobile', readonly=False, depends=(['partner_id']), store=True)
    sms_token = fields.Char('SMS Token', readonly=True)

    signature = fields.Binary(attachment=True)
    signing_date = fields.Date('Signed on', readonly=True)
    state = fields.Selection([
        ("sent", "To Sign"),
        ("refused", "Refused"),
        ("completed", "Completed"),
        ("canceled", "Canceled"),
    ], readonly=True, default="sent")
    color = fields.Integer(compute='_compute_color')

    signer_email = fields.Char(string='Email', compute="_compute_email", store=True)
    is_mail_sent = fields.Boolean(readonly=True, copy=False, help="The signature mail has been sent.")
    change_authorized = fields.Boolean(related='role_id.change_authorized')

    latitude = fields.Float(digits=(10, 7))
    longitude = fields.Float(digits=(10, 7))

    @api.constrains('signer_email')
    def _check_signer_email_validity(self):
        if any(sri.partner_id and not sri.signer_email for sri in self):
            raise ValidationError(_("All signers must have valid email addresses"))

    @api.constrains('partner_id', 'role_id')
    def _check_signers_validity(self):
        # this check allows one signer to be False, which is used to "share" a sign template
        for sign_request in self.sign_request_id:
            template_roles = sign_request.template_id.sign_item_ids.responsible_id
            sign_request_items = sign_request.request_item_ids
            if len(sign_request_items) != max(len(template_roles), 1) or \
                    set(sign_request_items.role_id.ids) != (set(template_roles.ids) if template_roles else set([self.env.ref('sign.sign_item_role_default').id])) or \
                    (len(sign_request_items) != len(sign_request_items.partner_id.ids) and len(sign_request_items) != 1):
                raise ValidationError(_("You must specify different signers for each role of your sign template"))

    def write(self, vals):
        if vals.get('partner_id') is False:
            raise UserError(_("You need to define a signatory"))
        request_items_reassigned = self.env['sign.request.item']
        if vals.get('partner_id'):
            request_items_reassigned |= self.filtered(lambda sri: self.partner_id.id != vals['partner_id'])
            if any(sri.state != 'sent'
                   or sri.sign_request_id.state != 'sent'
                   or (sri.partner_id and not sri.role_id.change_authorized)
                   for sri in request_items_reassigned):
                raise UserError(_("You cannot reassign this signatory"))
            new_sign_partner = self.env['res.partner'].browse(vals.get('partner_id'))
            old_sign_users = self.env['res.users'].search([
                ('partner_id.id', 'in', request_items_reassigned.partner_id.ids),
                ('groups_id', 'in', [self.env.ref('sign.group_sign_employee').id])
            ], limit=len(request_items_reassigned.partner_id))
            for request_item in request_items_reassigned:
                # remove old activities for internal users
                old_sign_user = old_sign_users.filtered(lambda usr: usr.partner_id.id == request_item.partner_id.id)
                if old_sign_user:
                    request_item.sign_request_id.activity_unlink(['mail.mail_activity_data_todo'], user_id=old_sign_user.id)
                # create logs
                request_item.sign_request_id.message_post(
                    body=_('The contact of %(role)s has been changed from %(old_partner)s to %(new_partner)s.',
                           role=request_item.role_id.name, old_partner=request_item.partner_id.name, new_partner=new_sign_partner.name))

            # add new followers
            request_items_reassigned.sign_request_id.message_subscribe(partner_ids=[vals.get('partner_id')])
            # add new activities for internal users
            new_sign_user = self.env['res.users'].search([
                ('partner_id.id', '=', vals.get('partner_id')),
                ('groups_id', 'in', [self.env.ref('sign.group_sign_employee').id])
            ], limit=1)
            if new_sign_user:
                self.sign_request_id.activity_update(new_sign_user)

        res = super(SignRequestItem, self).write(vals)

        # change access token
        for request_item in request_items_reassigned.filtered(lambda sri: sri.is_mail_sent):
            request_item.access_token = self._default_access_token()
            request_item.is_mail_sent = False
        return res

    def _cancel(self, no_access=True):
        for request_item in self:
            request_item.write({
                'access_token': self._default_access_token() if no_access else request_item.access_token,
                'state': 'canceled' if request_item.state == 'sent' else request_item.state,
                'signing_date': fields.Date.context_today(self) if request_item.state == 'sent' else request_item.signing_date,
                'is_mail_sent': False if no_access else request_item.is_mail_sent,
            })

    def action_completed(self):
        self.write({'signing_date': fields.Date.context_today(self), 'state': 'completed'})
        self.mapped('sign_request_id')._check_after_compute()

    def refuse(self, refusal_reason):
        self.ensure_one()
        if not self.env.su:
            raise UserError(_("This function can only be called with sudo."))
        if self.state != 'sent':
            raise UserError(_("This sign request item cannot be refused"))
        self.env['sign.log']._create_log(self, "refuse", is_request=False, token=self.access_token)
        self.write({'signing_date': fields.Date.context_today(self), 'state': 'refused'})
        refuse_user = self.env['res.users'].search([('partner_id', '=', self.partner_id.id)], limit=1)
        # mark the activity as done for the refuser
        if refuse_user.has_group('sign.group_sign_employee'):
            self.sign_request_id.activity_feedback(['mail.mail_activity_data_todo'], user_id=refuse_user.id)
        refusal_reason = _("No specified reason") if not refusal_reason or refusal_reason.isspace() else refusal_reason
        message_post = _("The signature has been refused by %s(%s)") % (self.partner_id.name, self.role_id.name)
        message_post = Markup('{}<p style="white-space: pre">{}</p>').format(message_post, refusal_reason)
        self.sign_request_id.message_post(body=message_post)
        self.sign_request_id._refuse(self.partner_id, refusal_reason)

    def _send_signature_access_mail(self):
        tpl = self.env.ref('sign.sign_template_mail_request')
        for signer in self:
            signer_lang = get_lang(self.env, lang_code=signer.partner_id.lang).code
            tpl = tpl.with_context(lang=signer_lang)
            body = tpl._render({
                'record': signer,
                'link': url_join(signer.get_base_url(), "sign/document/mail/%(request_id)s/%(access_token)s" % {'request_id': signer.sign_request_id.id, 'access_token': signer.access_token}),
                'subject': signer.sign_request_id.subject,
                'body': signer.sign_request_id.message if not is_html_empty(signer.sign_request_id.message) else False,
                'use_sign_terms': self.env['ir.config_parameter'].sudo().get_param('sign.use_sign_terms')
            }, engine='ir.qweb', minimal_qcontext=True)

            attachment_ids = signer.sign_request_id.attachment_ids.ids
            self.env['sign.request']._message_send_mail(
                body, 'mail.mail_notification_light',
                {'record_name': signer.sign_request_id.reference},
                {'model_description': 'signature', 'company': signer.create_uid.company_id},
                {'email_from': signer.create_uid.email_formatted,
                 'author_id': signer.create_uid.partner_id.id,
                 'email_to': formataddr((signer.partner_id.name, signer.signer_email)),
                 'attachment_ids': attachment_ids,
                 'subject': signer.sign_request_id.subject},
                force_send=True,
                lang=signer_lang,
            )
            signer.is_mail_sent = True

    def sign(self, signature, new_sign_items=None):
        """ Stores the sign request item values.
        :param signature: dictionary containing signature values and corresponding ids
        :param new_sign_items: dictionary containing new items added by the user while signing the document (edit while signing)
        """
        self.ensure_one()
        if not isinstance(signature, dict):
            self.signature = signature
        else:
            SignItemValue = self.env['sign.request.item.value']
            request = self.sign_request_id

            signer_items = request.template_id.sign_item_ids.filtered(lambda r: r.responsible_id.id == self.role_id.id)
            authorised_ids = set(signer_items.mapped('id'))
            required_ids = set(signer_items.filtered('required').mapped('id'))

            signature_ids = {int(k) for k in signature}
            if not new_sign_items:
                new_sign_items = {}
            new_sign_ids = {int(k) for k in new_sign_items.keys()}
            item_ids = signature_ids - new_sign_ids

            if not (item_ids <= authorised_ids and required_ids <= item_ids and (signature_ids - authorised_ids) == new_sign_ids): # Security check
                return False

            def check_new_sign_item_types(sign_items):
                sign_types = map(lambda d: d['type_id'], sign_items.values())
                allowed_types = [
                    self.env.ref('sign.sign_item_type_text').id,
                    self.env.ref('sign.sign_item_type_signature').id,
                    self.env.ref('sign.sign_item_type_initial').id
                ]
                return all(sign_type in allowed_types for sign_type in sign_types)

            # edit request template while signing
            if new_sign_ids and self.env['sign.request'].check_request_edit_during_sign(request.id) and check_new_sign_item_types(new_sign_items):
                old_template = request.template_id
                request.template_id = self.env['sign.template']._copy_edited_template(old_template.id, request.create_uid.id)

                new_items_signature = dict(filter(lambda item: int(item[0]) not in authorised_ids, signature.items()))
                old_items_signature = dict(filter(lambda item: int(item[0]) in authorised_ids, signature.items()))

                old_items_signature = self._get_existing_items_signature(old_template, old_items_signature)
                new_items_signature = self._get_new_items_signature(new_items_signature, new_sign_items)

                signature = dict(new_items_signature, **old_items_signature)

                self.env['sign.log']._create_log(request, "update", True, partner_id=self.partner_id.id)
                body = _("The signature request was edited by: %s.", self.partner_id.name)
                request.message_post(body=body)
            elif new_sign_ids:
                return False

            user = self.env['res.users'].search([('partner_id', '=', self.partner_id.id)], limit=1).sudo()
            for itemId in signature:
                item_value = SignItemValue.search([('sign_item_id', '=', int(itemId)), ('sign_request_id', '=', request.id)])
                if not item_value:
                    item_value = SignItemValue.create({'sign_item_id': int(itemId), 'sign_request_id': request.id,
                                                       'value': signature[itemId], 'sign_request_item_id': self.id})
                else:
                    item_value.write({'value': signature[itemId]})
                if item_value.sign_item_id.type_id.item_type == 'signature':
                    self.signature = signature[itemId][signature[itemId].find(',')+1:]

        return True

    def _get_existing_items_signature(self, old_template, signature):
        """ Copies the sign items from the old template and
            maps the signature dictionary keys to the new ids of the template.
            Used for the edit while signing feature.
            :param old_template: sign.template
            :param signature: dict with keys being the id of the sign.item and value being sign.item.value
            :returns new_signature: signature dict with the new ORM ids and their values
        """
        template = self.sign_request_id.template_id
        new_signature = {}
        new_template_sign_items = []
        for old_sign_item in old_template.sign_item_ids:
            current_id = old_sign_item.copy().id
            old_id = str(old_sign_item.id)
            if old_id in signature:
                new_signature[str(current_id)] = signature[old_id]
            new_template_sign_items.append(current_id)
        template.sign_item_ids = new_template_sign_items
        return new_signature

    def _get_new_items_signature(self, signature, new_sign_items):
        """ Creates new sign items and maps the signature dictionary keys
            to the new ORM-defined ids.
            Used for the edit while signing feature.
            :param signature: dictionary with keys being the id of the sign.item and value being sign.item.value
            :param new_sign_items: dictionary containing new items added by the user while signing the document (quick edit)
            :returns new_signature: signature dictionary containing the new ORM ids for the new_sign_items and their assigned values
        """
        template = self.sign_request_id.template_id

        new_signature = {}
        for new_sign_item_id, new_sign_item_value in new_sign_items.items():
            new_sign_item_value['template_id'] = template.id
            new_sign_item_value['option_ids'] = [(6, False, [int(op) for op in new_sign_item_value.get('option_ids', [])])]
            created_id = self.env['sign.item'].create(new_sign_item_value).id
            new_signature[str(created_id)] = signature[new_sign_item_id]
        return new_signature

    def send_signature_accesses(self):
        self.sign_request_id._check_senders_validity()
        self._send_signature_access_mail()
        for sign_request_item in self:
            body = _("The signature mail has been sent to: %s(%s)", sign_request_item.partner_id.name, sign_request_item.role_id.name)
            if not is_html_empty(sign_request_item.sign_request_id.message):
                body += sign_request_item.sign_request_id.message
            sign_request_item.sign_request_id.message_post(body=body, attachment_ids=sign_request_item.sign_request_id.attachment_ids.ids)

    def _reset_sms_token(self):
        for record in self:
            record.sms_token = randint(100000, 999999)

    def _send_sms(self):
        for rec in self:
            rec._reset_sms_token()
            self.env['sms.api']._send_sms([rec.sms_number], _('Your confirmation code is %s', rec.sms_token))

    def _compute_access_url(self):
        super(SignRequestItem, self)._compute_access_url()
        for signature_request in self:
            signature_request.access_url = '/my/signature/%s' % signature_request.id

    @api.depends('state')
    def _compute_color(self):
        color_map = {"canceled": 0,
                     "sent": 0,
                     "refused": 1,
                     "completed": 10}
        for sign_request_item in self:
            sign_request_item.color = color_map[sign_request_item.state]

    @api.depends('partner_id.email')
    def _compute_email(self):
        for sign_request_item in self.filtered(lambda sri: sri.state == "sent"):
            sign_request_item.signer_email = sign_request_item.partner_id.email_normalized


class SignRequestItemValue(models.Model):
    _name = "sign.request.item.value"
    _description = "Signature Item Value"
    _rec_name = 'sign_request_id'

    sign_request_item_id = fields.Many2one('sign.request.item', string="Signature Request item", required=True,
                                           ondelete='cascade')
    sign_item_id = fields.Many2one('sign.item', string="Signature Item", required=True, ondelete='cascade')
    sign_request_id = fields.Many2one(string="Signature Request", required=True, ondelete='cascade', related='sign_request_item_id.sign_request_id')

    value = fields.Text()
