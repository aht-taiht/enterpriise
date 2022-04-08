# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import OrderedDict

from odoo import api, fields, models

class Document(models.Model):
    _inherit = 'documents.document'

    is_shared = fields.Boolean(compute='_compute_is_shared')

    def _compute_is_shared(self):
        search_domain = [
            '&',
                '|',
                    ('date_deadline', '=', False),
                    ('date_deadline', '>', fields.Date.today()),
                '&',
                    ('type', '=', 'ids'),
                    ('document_ids', 'in', self.ids),
        ]

        doc_share_read_group = self.env['documents.share']._read_group(
            search_domain,
            ['document_ids'],
            ['document_ids'],
        )
        doc_share_count_per_doc_id = {res['document_ids'][0]: res['document_ids_count'] for res in doc_share_read_group}

        for document in self:
            document.is_shared = doc_share_count_per_doc_id.get(document.id) or document.folder_id.is_shared

    @api.model
    def search_panel_select_range(self, field_name, **kwargs):
        if field_name != 'folder_id' or not self._context.get('limit_folders_to_project'):
            return super().search_panel_select_range(field_name, **kwargs)

        res_model = self._context.get('active_model')
        if res_model not in ('project.project', 'project.task'):
            return super().search_panel_select_range(field_name, **kwargs)

        res_id = self._context.get('active_id')
        fields = ['display_name', 'description', 'parent_folder_id']

        project = self.env['project.project'].browse(res_id) \
            if res_model == 'project.project' \
            else self.env['project.task'].browse(res_id).project_id

        document_read_group = self.env['documents.document']._read_group(kwargs.get('search_domain', []), ['folder_ids:array_agg(folder_id)'], [])
        folder_ids = (document_read_group[0]['folder_ids'] if document_read_group else []) or []
        records = self.env['documents.folder'].with_context(hierarchical_naming=False).search_read([
            '|',
                ('id', 'child_of', project.documents_folder_id.id),
                ('id', 'in', folder_ids),
        ], fields)
        available_folder_ids = set(record['id'] for record in records)

        values_range = OrderedDict()
        for record in records:
            record_id = record['id']
            if record['parent_folder_id'] not in available_folder_ids:
                record['parent_folder_id'] = False
            value = record['parent_folder_id']
            record['parent_folder_id'] = value and value[0]
            values_range[record_id] = record

        return {
            'parent_field': 'parent_folder_id',
            'values': list(values_range.values()),
        }
