# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import difflib
import io
from collections import defaultdict
from lxml import etree
from lxml.builder import E
import json
import uuid
import random

from odoo import api, models, _
from odoo.exceptions import UserError
from odoo.osv import expression


CONTAINER_TYPES = (
    'group', 'page', 'sheet', 'div', 'ul', 'li', 'notebook',
)



class View(models.Model):
    _name = 'ir.ui.view'
    _description = 'View'
    _inherit = ['studio.mixin', 'ir.ui.view']

    TEMPLATE_VIEWS_BLACKLIST = [
        'web.html_container',
        'web.report_layout',
        'web.external_layout',
        'web.internal_layout',
        'web.basic_layout',
        'web.minimal_layout',
        'web.external_layout_background',
        'web.external_layout_boxed',
        'web.external_layout_clean',
        'web.external_layout_standard',
    ]

    def _apply_groups(self, node, name_manager, node_info):
        # apply_group only returns the view groups ids.
        # As we need also need their name and display in Studio to edit these groups
        # (many2many widget), they have been added to node (only in Studio). Also,
        # we need ids of the fields inside map view(that displays marker popup) to edit
        # them with similar many2many widget. So we also add them to node (only in Studio).
        # This preprocess cannot be done at validation time because the
        # attributes `studio_groups` and `studio_map_field_ids` are not RNG valid.
        if self._context.get('studio') and not name_manager.validate:
            if node.get('groups'):
                self.set_studio_groups(node)
            if node.tag == 'map':
                self.set_studio_map_popup_fields(name_manager.Model._name, node)

        return super(View, self)._apply_groups(node, name_manager, node_info)

    @api.model
    def set_studio_groups(self, node):
        studio_groups = []
        for xml_id in node.attrib['groups'].split(','):
            group = self.env['ir.model.data'].xmlid_to_object(xml_id)
            if group:
                studio_groups.append({
                    "id": group.id,
                    "name": group.name,
                    "display_name": group.display_name
                })
        node.attrib['studio_groups'] = json.dumps(studio_groups)

    @api.model
    def set_studio_map_popup_fields(self, model, node):
        field_names = [field.get('name') for field in node.findall('field')]
        field_ids = self.env['ir.model.fields'].search([('model', '=', model), ('name', 'in', field_names)]).ids
        if field_ids:
            node.attrib['studio_map_field_ids'] = json.dumps(field_ids)

    @api.model
    def create_automatic_views(self, res_model):
        """Generates automatic views for the given model depending on its fields."""
        model = self.env[res_model]
        views = self.env['ir.ui.view']
        # form, list and search: always
        views |= self.auto_list_view(res_model)
        views |= self.auto_form_view(res_model)
        views |= self.auto_search_view(res_model)
        # calendar: only if x_studio_date
        if 'x_studio_date' in model._fields:
            views |= self.auto_calendar_view(res_model)
        # gantt: only if x_studio_date_start & x_studio_date_stop
        if 'x_studio_date_start' in model._fields and 'x_studio_date_stop' in model._fields:
            views |= self.auto_gantt_view(res_model)
        # kanban: only if x_studio_stage_id
        if 'x_studio_stage_id' in model._fields:
            views |= self.auto_kanban_view(res_model)
        # map: only if x_studio_partner_id
        if 'x_studio_partner_id' in model._fields:
            views |= self.auto_map_view(res_model)
        # pivot: only if x_studio_value
        if 'x_studio_value' in model._fields:
            views |= self.auto_pivot_view(res_model)
        return views

    def auto_list_view(self, res_model):
        model = self.env[res_model]
        rec_name = model._rec_name_fallback()
        fields = list()
        if 'x_studio_sequence' in model._fields and not 'x_studio_priority' in model._fields:
            fields.append(E.field(name='x_studio_sequence', widget='handle'))
        fields.append(E.field(name=rec_name))
        if 'x_studio_partner_id' in model._fields:
            fields.append(E.field(name='x_studio_partner_id'))
        if 'x_studio_user_id' in model._fields:
            fields.append(E.field(name='x_studio_user_id', widget='many2one_avatar_user'))
        if 'x_studio_company_id' in model._fields:
            fields.append(E.field(name='x_studio_company_id', groups='base.group_multi_company'))
        if 'x_studio_currency_id' in model._fields and 'x_studio_value' in model._fields:
            fields.append(E.field(name='x_studio_currency_id', invisible='1'))
            fields.append(E.field(name='x_studio_value', widget='monetary', options="{'currency_field': 'x_studio_currency_id'}", sum=_("Total")))
        if 'x_studio_tag_ids' in model._fields:
            fields.append(E.field(name='x_studio_tag_ids', widget='many2many_tags', options="{'color_field': 'x_color'}"))
        if 'x_color' in model._fields:
            fields.append(E.field(name='x_color', widget='color_picker'))
        tree_params = {} if not self._context.get('list_editable') else {'editable': self._context.get('list_editable')}
        tree = E.tree(**tree_params)
        tree.extend(fields)
        arch = etree.tostring(tree, encoding='unicode', pretty_print=True)

        return self.create({
            'type': 'tree',
            'model': res_model,
            'arch': arch,
            'name': "Default %s view for %s" % ('list', res_model),
        })

    def auto_form_view(self, res_model):
        ir_model = self.env['ir.model'].search([('model', '=', res_model)])
        model = self.env[res_model]
        rec_name = model._rec_name_fallback()
        sheet_content = list()
        header_content = list()
        if 'x_studio_stage_id' in model._fields:
            header_content.append(E.field(name='x_studio_stage_id', widget='statusbar', clickable='1'))
            sheet_content.append(E.field(name='x_studio_kanban_state', widget='state_selection'))
        if 'x_active' in model._fields:
            sheet_content.append(E.widget(name='web_ribbon', text=_('Archived'), bg_color='bg-danger', attrs="{'invisible': [('x_active', '=', True)]}"))
            sheet_content.append(E.field(name='x_active', invisible='1'))
        if 'x_studio_image' in model._fields:
            sheet_content.append(E.field({'class': 'oe_avatar', 'widget': 'image', 'name': 'x_studio_image'}))
        title = etree.fromstring("""
            <div class="oe_title">
                <h1>
                    <field name="%(field_name)s" required="1" placeholder="Name..."/>
                </h1>
            </div>
        """ % {'field_name': rec_name})
        sheet_content.append(title)
        group_name = 'studio_group_' + str(uuid.uuid4())[:6]
        left_group = E.group(name=group_name + '_left')
        right_group = E.group(name=group_name + '_right')
        left_group_content, right_group_content = list(), list()
        if 'x_studio_user_id' in model._fields:
            right_group_content.append(E.field(name='x_studio_user_id', widget='many2one_avatar_user'))
        if 'x_studio_partner_id' in model._fields:
            left_group_content.append(E.field(name='x_studio_partner_id'))
            left_group_content.append(E.field(name='x_studio_partner_phone', widget='phone', options="{'enable_sms': True}"))
            left_group_content.append(E.field(name='x_studio_partner_email', widget='email'))
        if 'x_studio_currency_id' in model._fields and 'x_studio_value' in model._fields:
            right_group_content.append(E.field(name='x_studio_currency_id', invisible='1'))
            right_group_content.append(E.field(name='x_studio_value', widget='monetary', options="{'currency_field': 'x_studio_currency_id'}"))
        if 'x_studio_tag_ids' in model._fields:
            right_group_content.append(E.field(name='x_studio_tag_ids', widget='many2many_tags', options="{'color_field': 'x_color'}"))
        if 'x_studio_company_id' in model._fields:
            right_group_content.append(E.field(name='x_studio_company_id', groups='base.group_multi_company', options="{'no_create': True}"))
        if 'x_studio_date' in model._fields:
            left_group_content.append(E.field(name='x_studio_date'))
        if 'x_studio_date_start' in model._fields and 'x_studio_date_stop' in model._fields:
            left_group_content.append(E.label({'for': "x_studio_date_start"}, string='Dates'))
            daterangeDiv = E.div({'class': 'o_row'})
            daterangeDiv.append(E.field(name='x_studio_date_start', widget='daterange', options='{"related_end_date": "x_studio_date_stop"}'))
            daterangeDiv.append(E.span(_(' to ')))
            daterangeDiv.append(E.field(name='x_studio_date_stop', widget='daterange', options='{"related_start_date": "x_studio_date_start"}'))
            left_group_content.append(daterangeDiv)
        if not left_group_content:
            # there is nothing in our left group; switch the groups' content
            # to avoid a weird looking form view
            left_group_content = right_group_content
            right_group_content = list()
        left_group.extend(left_group_content)
        right_group.extend(right_group_content)
        sheet_content.append(E.group(left_group, right_group, name=group_name))
        if 'x_studio_notes' in model._fields:
            sheet_content.append(E.group(E.field(name='x_studio_notes', placeholder=_('Type down your notes here...'), nolabel='1')))
        form = E.form(E.header(*header_content), E.sheet(*sheet_content, string=model._description))
        chatter_widgets = list()
        if ir_model.is_mail_thread:
            chatter_widgets.append(E.field(name='message_follower_ids', widget='mail_followers'))
            chatter_widgets.append(E.field(name='message_ids', widget='mail_thread'))
        if ir_model.is_mail_activity:
            chatter_widgets.append(E.field(name='activity_ids', widget='mail_activity'))
        if chatter_widgets:
            chatter_div = E.div({'class': 'oe_chatter', 'name': 'oe_chatter'})
            chatter_div.extend(chatter_widgets)
            form.append(chatter_div)
        arch = etree.tostring(form, encoding='unicode', pretty_print=True)

        return self.create({
            'type': 'form',
            'model': res_model,
            'arch': arch,
            'name': "Default %s view for %s" % ('form', res_model),
        })

    def auto_search_view(self, res_model):
        model = self.env[res_model]
        rec_name = model._rec_name_fallback()
        fields = list()
        filters = list()
        groupbys = list()
        fields.append(E.field(name=rec_name))
        if 'x_studio_partner_id' in model._fields:
            fields.append(E.field(name='x_studio_partner_id', operator='child_of'))
            groupbys.append(E.filter(name='groupby_x_partner', string=_('Partner'), context="{'group_by': 'x_studio_partner_id'}", domain="[]"))
        if 'x_studio_user_id' in model._fields:
            fields.append(E.field(name='x_studio_user_id'))
            filters.append(E.filter(string=_('My %s') % model._description, name='my_%s' % res_model, domain="[['x_studio_user_id', '=', uid]]"))
            groupbys.append(E.filter(name='groupby_x_user', string=_('Responsible'), context="{'group_by': 'x_studio_user_id'}", domain="[]"))
        date_filters = []
        if 'x_studio_date' in model._fields:
            date_filters.append(E.filter(date='x_studio_date', name='studio_filter_date', string=_('Date')))
        if 'x_studio_date_start' in model._fields and 'x_studio_date_stop' in model._fields:
            date_filters.append(E.filter(date='x_studio_date_start', name='studio_filter_date_start', string=_('Start Date')))
            date_filters.append(E.filter(date='x_studio_date_stop', name='studio_filter_date_stop', string=_('End Date')))
        if date_filters:
            filters.append(E.separator())
            filters.extend(date_filters)
        if 'x_active' in model._fields:
            filters.append(E.separator())
            filters.append(E.filter(string=_('Archived'), name='archived_%s' % res_model, domain="[['x_active', '=', False]]"))
            filters.append(E.separator())
        if 'x_studio_tag_ids' in model._fields:
            fields.append(E.field(name='x_studio_tag_ids'))
        if 'x_studio_stage_id' in model._fields:
            groupbys.append(E.filter(name='x_studio_stage_id', string=_('Stage'), context="{'group_by': 'x_studio_stage_id'}", domain="[]"))
        search = E.search(*fields)
        search.extend(filters)
        if groupbys:
            groupby = E.group(expand="0", string=_('Group By'))
            groupby.extend(groupbys)
            search.extend(groupby)
        arch = etree.tostring(search, encoding='unicode', pretty_print=True)

        return self.create({
            'type': 'search',
            'model': res_model,
            'arch': arch,
            'name': "Default %s view for %s" % ('search', res_model),
        })

    def auto_calendar_view(self, res_model):
        model = self.env[res_model]
        if not 'x_studio_date' in model._fields:
            return self
        calendar = E.calendar(date_start='x_studio_date')
        arch = etree.tostring(calendar, encoding='unicode', pretty_print=True)

        return self.create({
            'type': 'calendar',
            'model': res_model,
            'arch': arch,
            'name': "Default %s view for %s" % ('calendar', res_model),
        })

    def auto_gantt_view(self, res_model):
        gantt = E.gantt(date_start='x_studio_date_start', date_stop='x_studio_date_stop')
        arch = etree.tostring(gantt, encoding='unicode', pretty_print=True)

        return self.create({
            'type': 'gantt',
            'model': res_model,
            'arch': arch,
            'name': "Default %s view for %s" % ('gantt', res_model),
        })

    def auto_map_view(self, res_model):
        field = E.field(name='x_studio_partner_id', string=_('Partner'))
        map_view = E.map(field, res_partner='x_studio_partner_id')
        arch = etree.tostring(map_view, encoding='unicode', pretty_print=True)

        return self.create({
            'type': 'map',
            'model': res_model,
            'arch': arch,
            'name': "Default %s view for %s" % ('map', res_model),
        })

    def auto_pivot_view(self, res_model):
        model = self.env[res_model]
        fields = list()
        fields.append(E.field(name='x_studio_value', type='measure'))
        if 'x_studio_stage_id' in model._fields:
            fields.append(E.field(name='x_studio_stage_id', type='col'))
        if 'x_studio_date' in model._fields:
            fields.append(E.field(name='x_studio_date', type='row'))
        pivot = E.pivot()
        pivot.extend(fields)
        arch = etree.tostring(pivot, encoding='unicode', pretty_print=True)

        return self.create({
            'type': 'pivot',
            'model': res_model,
            'arch': arch,
            'name': "Default %s view for %s" % ('pivot', res_model),
        })

    def auto_kanban_view(self, res_model):
        model = self.env[res_model]
        pre_fields = list()  # fields not used in a t-field node but needed for display
        content_div = E.div({'class': "o_kanban_record_details"})
        title = E.strong({'class': 'o_kanban_record_title', 'name': 'studio_auto_kanban_title'})
        title.append(E.field(name=model._rec_name_fallback()))
        headers_div = E.div({'class': 'o_kanban_record_headings', 'name': 'studio_auto_kanban_headings'})
        headers_div.append(E.field(name='x_studio_priority', widget='boolean_favorite', nolabel='1'))
        headers_div.append(title)
        dropdown_div = E.div({'class': 'o_dropdown_kanban dropdown'})
        dropdown_toggle = E.a({
            'role': 'button',
            'class': 'dropdown-toggle o-no-caret btn',
            'data-toggle': 'dropdown',
            'data-display': 'static',
            'href': '#',
            'aria-label': _('Dropdown Menu'),
            'title': _('Dropdown Menu'),
            })
        dropdown_toggle.append(E.span({'class': 'fa fa-ellipsis-v'}))
        dropdown_menu = E.div({'class': 'dropdown-menu', 'role': 'menu'})
        dropdown_menu.extend([
            E.a({'t-if': 'widget.editable', 'role': 'menuitem', 'type': 'edit', 'class': 'dropdown-item'},_('Edit')),
            E.a({'t-if': 'widget.deletable', 'role': 'menuitem', 'type': 'delete', 'class': 'dropdown-item'}, _('Delete'))
        ])
        dropdown_div.extend([dropdown_toggle, dropdown_menu])
        top_div = E.div({'class': 'o_kanban_record_top', 'name': 'studio_auto_kanban_top'})
        top_div.extend([headers_div, dropdown_div])
        body_div = E.div({'class': 'o_kanban_record_body', 'name': 'studio_auto_kanban_body'})
        bottom_div = E.div({'class': 'o_kanban_record_bottom', 'name': 'studio_auto_kanban_bottom'})
        bottom_left_div = E.div({'class': 'oe_kanban_bottom_left', 'name': 'studio_auto_kanban_bottom_left'})
        bottom_right_div = E.div({'class': 'oe_kanban_bottom_right', 'name': 'studio_auto_kanban_bottom_right'})
        bottom_div.extend([bottom_left_div, bottom_right_div])
        bottom_right_div.append(E.field(name='x_studio_kanban_state', widget='state_selection'))
        if 'x_studio_user_id' in model._fields:
            pre_fields.append(E.field(name='x_studio_user_id', widget="many2one_avatar_user"))
            unassigned_var = E.t({'t-set': 'unassigned'})
            unassigned_var.append(E.t({'t-esc': "_t('Unassigned')"}))
            img = E.img({'t-att-src': "kanban_image('res.users', 'image_128', record.x_studio_user_id.raw_value)",
                         't-att-title': "record.x_studio_user_id.value || unassigned",
                         't-att-alt': "record.x_studio_user_id.value",
                         'class': "oe_kanban_avatar o_image_24_cover float-right"})
            bottom_right_div.append(unassigned_var)
            bottom_right_div.append(img)
        content_div.extend([top_div, body_div, bottom_div])
        card_div = E.div({'class': "o_kanban_record oe_kanban_global_click o_kanban_record_has_image_fill"})
        if 'x_studio_value' and 'x_studio_currency_id' in model._fields:
            pre_fields.append(E.field(name='x_studio_currency_id'))
            bottom_left_div.append(E.field(name='x_studio_value', widget='monetary', options="{'currency_field': 'x_studio_currency_id'}"))
        if 'x_studio_tag_ids' in model._fields:
            body_div.append(E.field(name='x_studio_tag_ids', options="{'color_field': 'x_color'}"))
        if 'x_studio_image' in model._fields:
            image_field = E.field({
                'class': 'o_kanban_image_fill_left',
                'name': 'x_studio_image',
                'widget': 'image',
                'options': '{"zoom": true, "background": true, "preventClicks": false}'
            })
            card_div.append(image_field)
        card_div.append(content_div)
        kanban_box = E.t(card_div, {'t-name': "kanban-box"})
        templates = E.templates(kanban_box)
        order = 'x_studio_priority desc, x_studio_sequence asc, id desc' if 'x_studio_sequence' in model._fields else 'x_studio_priority desc, id desc'
        kanban = E.kanban(default_group_by='x_studio_stage_id', default_order=order)
        kanban.extend(pre_fields)
        if 'x_studio_value' in model._fields:
            progressbar = E.progressbar(field='x_studio_kanban_state', colors='{"normal": "muted", "done": "success", "blocked": "danger"}', sum_field='x_studio_value')
        else:
            progressbar = E.progressbar(field='x_studio_kanban_state', colors='{"normal": "muted", "done": "success", "blocked": "danger"}')
        kanban.append(progressbar)
        kanban.append(templates)
        arch = etree.tostring(kanban, encoding='unicode', pretty_print=True)

        return self.create({
            'type': 'kanban',
            'model': res_model,
            'arch': arch,
            'name': "Default %s view for %s" % ('kanban', res_model),
        })

    # Returns "true" if the view_id is the id of the studio view.
    def _is_studio_view(self):
        return self.xml_id.startswith('studio_customization')

    # Based on inherit_branding of ir_ui_view
    # This will add recursively the groups ids on the spec node.
    def _groups_branding(self, specs_tree):
        groups_id = self.groups_id
        studio = self.env.context.get('studio')
        check_view_ids = self.env.context.get('check_view_ids')
        if groups_id and (not studio or not check_view_ids):
            attr_value = ','.join(map(str, groups_id.ids))
            for node in specs_tree.iter(tag=etree.Element):
                node.set('studio-view-group-ids', attr_value)

    # Used for studio views only.
    # This studio view specification will not always be available.
    # So, we add the groups name to find out when they will be available.
    # This information will be used in Studio to inform the user.
    def _set_groups_info(self, node, group_ids):
        groups = self.env['res.groups'].browse(map(int, group_ids.split(',')))
        view_group_names = ','.join(groups.mapped('name'))
        for child in node.iter(tag=etree.Element):
            child.set('studio-view-group-names', view_group_names)
            child.set('studio-view-group-ids', group_ids)

    # Used for studio views only.
    # Check if the hook node depends of groups.
    def _check_parent_groups(self, source, spec):
        node = self.locate_node(source, spec)
        if node is not None and node.get('studio-view-group-ids'):
            # Propogate group info for all children
            self._set_groups_info(spec, node.get('studio-view-group-ids'))

    # Used for studio views only.
    # Apply spec by spec studio view.
    def _apply_studio_specs(self, source, specs_tree):
        for spec in specs_tree.iterchildren(tag=etree.Element):
            if self._context.get('studio'):
                # Detect xpath base on a field added by a view with groups
                self._check_parent_groups(source, spec)
                # Here, we don't want to catch the exception.
                # This mechanism doesn't save the view if something goes wrong.
                source = super(View, self).apply_inheritance_specs(source, spec)
            else:
                # Avoid traceback if studio view and skip xpath when studio mode is off
                try:
                    source = super(View, self).apply_inheritance_specs(source, spec)
                except ValueError:
                    # 'locate_node' already log this error.
                    pass
        return source

    def apply_inheritance_specs(self, source, specs_tree):
        # Add branding for groups if studio mode is on
        if self._context.get('studio'):
            self._groups_branding(specs_tree)

        # If this is studio view, we want to apply it spec by spec
        if self._is_studio_view():
            return self._apply_studio_specs(source, specs_tree)
        else:
            # Remove branding added by '_groups_branding' before locating a node
            pre_locate = lambda arch: arch.attrib.pop("studio-view-group-ids", None)
            return super(View, self).apply_inheritance_specs(source, specs_tree,
                                                                pre_locate=pre_locate)

    def normalize(self):
        """
        Normalizes the studio arch by comparing the studio view to the base view
        and combining as many xpaths as possible in order to have a more compact
        final view

        Returns the normalized studio arch
        """
        # Beware ! By its reasoning, this function assumes that the view you
        # want to normalize is the last one to be applied on its root view.
        # This could be improved by deactivating all views that would be applied
        # after this one when calling the read_combined to get the old_view then
        # re-enabling them all afterwards.


        def is_moved(node):
            """ Helper method that determines if a node is a moved field."""
            return node.tag == 'field' and node.get('name') in moved_fields

        # Fetch the root view
        root_view = self
        while root_view.mode != 'primary':
            root_view = root_view.inherit_id

        parser = etree.XMLParser(remove_blank_text=True)
        new_view = root_view.read_combined()['arch']

        # Get the result of the xpath applications without this view
        self.active = False
        old_view = root_view.read_combined()['arch']
        self.active = True

        # The parent data tag is missing from read_combined
        new_view_tree = etree.Element('data')
        new_view_tree.append(etree.parse(io.StringIO(new_view), parser).getroot())
        old_view_tree = etree.Element('data')
        old_view_tree.append(etree.parse(io.StringIO(old_view), parser).getroot())
        new_view_arch_string = self._stringify_view(new_view_tree)
        old_view_arch_string = self._stringify_view(old_view_tree)
        diff = difflib.ndiff(old_view_arch_string.split('\n'), new_view_arch_string.split('\n'))

        # Format of difflib.ndiff output is:
        #   unchanged
        # - removed
        # + added
        # ? details
        # <empty line after details>
        #   unchanged

        old_view_iterator = old_view_tree.iter()
        new_view_iterator = new_view_tree.iter()

        # Determine which fields have moved. This information will be used to
        # compute the second diff because the moved nodes must appear in the
        # diff (see @stringify_node).
        removed_fields = {}
        added_fields = {}
        moved_fields = {}
        changes = {
            '-': [],
            '+': []
        }
        moving_boundary = None
        node = None

        def store_field(operation):
            if operation == '-':
                node = next(old_view_iterator)
                if node.tag == 'field':
                    removed_fields[node.get('name')] = node
            elif operation == '+':
                node = next(new_view_iterator)
                if node.tag == 'field':
                    added_fields[node.get('name')] = node

        for line in diff:
            if line.strip() and not line.startswith('?'):
                if line.startswith('-') or line.startswith('+'):
                    operation, line = line.split(' ', 1)
                    nodes = changes[operation]

                    if line.endswith('[@closed]') and nodes and nodes[-1] + '[@closed]' == line:
                        # This is the closing of a node we were operating on.
                        # It is not a candidate for moving boundary.
                        nodes.pop()

                    elif moving_boundary and moving_boundary != operation:
                        # We are already in a moving boundary mode.
                        # Look into the corresponding nodes for a match.
                        nodes = changes.get(moving_boundary)

                        if nodes and line == nodes[0]:
                            # The node matches the current moving boundary.
                            # We can stop watching this node.
                            nodes.pop(0)

                            if not nodes:
                                # The moving boundary is over as we found
                                # all its nodes twice.
                                moving_boundary = None

                        if not line.endswith('[@closed]'):
                            # If we are operating on a field, let's store it.
                            store_field(operation)

                    elif line.endswith('[@closed]'):
                        # We are operating on the closing of a node that
                        # we are not not operating on ! Moving boundary !
                        nodes.append(line)
                        moving_boundary = operation

                    else:
                        # Store this node to match when we close it.
                        nodes.append(line)

                        # If we are operating on a field, let's store it.
                        store_field(operation)

                else:
                    # This node seemingly has not moved.
                    if not line.endswith('[@closed]'):
                        # Only the nodes can be moved, we ignore the closings
                        old_node = next(old_view_iterator)
                        node = next(new_view_iterator)
                        # If we are in moving boundary mode, then this node
                        # definitely moved, since the boundary moved around it !
                        if moving_boundary and node.tag == 'field':
                            # Only fields are currently supported.
                            removed_fields[node.get('name')] = old_node
                            added_fields[node.get('name')] = node

        # Look at the fields we decided to watch. If they were both
        # removed and added, it means they have been moved.
        for name in removed_fields:
            if name in added_fields:
                moved_fields[name] = {
                    'old': removed_fields[name],
                    'new': added_fields[name],
                }

        # Recreate the trees as they have been modified during the first processing
        new_view_tree = etree.Element('data')
        new_view_tree.append(etree.parse(io.StringIO(new_view), parser).getroot())
        old_view_tree = etree.Element('data')
        old_view_tree.append(etree.parse(io.StringIO(old_view), parser).getroot())
        old_view_iterator = old_view_tree.iter()
        new_view_iterator = new_view_tree.iter()
        new_view_arch_string = self._stringify_view(new_view_tree, moved_fields)
        old_view_arch_string = self._stringify_view(old_view_tree)
        diff = difflib.ndiff(old_view_arch_string.split('\n'), new_view_arch_string.split('\n'))

        # Keep track of nameless elements with more than 1 occurrence
        nameless_count = defaultdict(int)
        for node in new_view_tree.iter():
            if not node.get('name'):
                nameless_count[node.tag] += 1

        arch = etree.Element('data')
        xpath = etree.Element('xpath')
        for line in diff:
            # Ignore details lines and [@closed] that are used so diff has correct order
            if line.strip() and not line.startswith('?') and not line.endswith('[@closed]'):
                line = line.replace('[@moved]', '')
                if line.startswith('-'):
                    node = next(old_view_iterator)

                    if node.tag == 'attribute':
                        continue

                    if is_moved(node) or \
                            any([is_moved(x) for x in node.iterancestors()]):
                        # nothing to do here, the node will be moved in the '+'
                        continue

                    # If we are already writing an xpath, we need to either
                    # close it or ignore this line
                    if xpath.get('expr'):
                        # Maybe we are already removing the parent of this
                        # node so this one will be removed automatically
                        current_xpath_target = next(iter(old_view_tree.xpath('.' + xpath.get('expr'))), None)
                        if xpath.get('position') == 'replace' and \
                                current_xpath_target in node.iterancestors():
                            continue
                        # If we are already adding stuff just before this node,
                        # we could as well replace it directly by what we want to add
                        # Also take care not to close the xpath is we are still
                        # in the attributes section of a given node
                        elif ((node.tag != 'attributes' and xpath.get('position') != 'after') or
                                (node.tag == 'attributes' and xpath.get('position') != 'attributes')):
                            # Consecutive removals need different xpath
                            xpath = self._close_and_get_new(arch, xpath)

                    xpath.attrib['expr'] = self._node_to_xpath(node)
                    if node.tag == 'attributes':
                        xpath.attrib['position'] = 'attributes'
                        # The attribute is removed
                        etree.SubElement(xpath, 'attribute', {'name': node.get('name')})
                    else:
                        xpath.attrib['position'] = 'replace'

                elif line.startswith('+'):
                    node = next(new_view_iterator)

                    # if there is more than one element with this tag and it doesn't have a way
                    # to identify itself, give it a name
                    if (node.tag in CONTAINER_TYPES
                            and nameless_count[node.tag] > 1
                            and not node.get('name')):
                        uid = str(uuid.UUID(int=random.getrandbits(128)))[:6]
                        node.attrib['name'] = 'studio_%s_%s' % (node.tag, uid)

                    if node.tag == 'attributes':
                        continue

                    if any([is_moved(x) for x in node.iterancestors()]):
                        # moved attributes will be computed afterwards because
                        # the move xpaths don't support children
                        # (see @get_node_attributes_diff)
                        continue

                    # The node for which this is the attribute may have been
                    # added by studio, in which case we don't need a new
                    # xpath to handle it properly
                    if node.tag == 'attribute' and self._get_node_from_xpath(xpath, node.getparent().getparent(), moved_fields) is not None:
                        continue

                    anchor_node = self._get_anchor_node(arch, xpath, node, moved_fields)

                    if anchor_node.tag == 'xpath' and not anchor_node.get('expr'):
                        # If the current xpath was not compatible, it has been
                        # closed and a new one has been generated
                        xpath = anchor_node
                        xpath.attrib['expr'], xpath.attrib['position'] = self._closest_node_to_xpath(node, old_view_tree, moved_fields)

                    if node.tag == 'field' and node.get('name') in moved_fields:
                        # manually replace the node by the `move` xpath
                        node = etree.Element('xpath', {
                            'expr': self._node_to_xpath(moved_fields[node.get('name')]['old']),
                            'position': 'move',
                        })

                    self._clone_and_append_to(node, anchor_node)

                else:
                    old_node = next(old_view_iterator)
                    next(new_view_iterator)
                    # This is an unchanged line, if an xpath is ungoing, close it.
                    if old_node.tag not in ['attribute', 'attributes']:
                        if xpath.get('expr'):
                            xpath = self._close_and_get_new(arch, xpath)

        # Append last remaining xpath if needed
        if xpath.get('expr') is not None:
            self._add_xpath_to_arch(arch, xpath)

        def get_node_attributes_diff(node1, node2):
            """ Computes the differences of attributes between two nodes."""
            diff = {}
            for attr in node1.attrib:
                if attr not in node2.attrib:
                    diff[attr] = ''
                elif node1.attrib[attr] != node2.attrib[attr]:
                    diff[attr] = node2.attrib[attr]
            for attr in dict(node2.attrib).keys() - dict(node1.attrib).keys():
                diff[attr] = node2.attrib[attr]
            return diff

        # Add xpath attributes for moved fields
        for f in moved_fields:
            old_node = moved_fields[f]['old']
            new_node = moved_fields[f]['new']
            attrs_diff = get_node_attributes_diff(old_node, new_node)
            if len(attrs_diff):
                xpath = etree.Element('xpath')
                xpath.attrib['expr'] = self._node_to_xpath(new_node)
                xpath.attrib['position'] = 'attributes'
                # alphabetically sort attributes by name
                node_attributes = sorted(attrs_diff.keys())
                for attr in node_attributes:
                    etree.SubElement(xpath, 'attribute', {
                        'name': attr,
                    }).text = attrs_diff[attr]
                self._add_xpath_to_arch(arch, xpath)

        normalized_arch = etree.tostring(self._indent_tree(arch), encoding='unicode') if len(arch) else u''
        return normalized_arch

    def _close_and_get_new(self, arch, xpath):
        self._add_xpath_to_arch(arch, xpath)
        return etree.Element('xpath')

    def _get_anchor_node(self, arch, xpath, node, moved_fields):
        """
        Check if a node can be merged inside an existing xpath

        Returns True if the node can be fit inside the given xpath, False otherwise
        """
        # Not compatible is either:
        # - position != attributes when node is an attribute
        # - position == attributes when node is not an attribute
        # - the node we want to add is not contiguous with the current xpath,
        #   which means the current xpath is not empty and the node preceding
        #   the one we we want to add is not in the xpath

        if not len(xpath):
            return xpath

        if xpath.get('position') == 'attributes':
            if node.tag == 'attribute':
                return xpath
            else:
                return self._close_and_get_new(arch, xpath)

        # If the preceding node or the parent is in the current xpath, we can append to it
        anchor_node = node.getprevious()
        if (anchor_node is not None and anchor_node.tag not in ['attribute', 'attributes']):
            studio_previous_node = self._get_node_from_xpath(xpath, anchor_node, moved_fields)
            if studio_previous_node is not None:
                return studio_previous_node.getparent()
            else:
                return self._close_and_get_new(arch, xpath)

        else:
            anchor_node = node.getparent()
            if anchor_node.tag == 'attributes':
                anchor_node = anchor_node.getparent()

            if node.tag == 'field' and node.get('name') in moved_fields:
                # Parent node of a moved field xpath must be the xpath of the new targeted position
                return self._close_and_get_new(arch, xpath)

            studio_parent_node = self._get_node_from_xpath(xpath, anchor_node, moved_fields)
            if studio_parent_node is not None:
                return studio_parent_node
            else:
                return self._close_and_get_new(arch, xpath)

    def _get_node_from_xpath(self, xpath, node, moved_fields):
        """
        Get a node from within an xpath if it exists

        Returns a node if it exists within the given xpath, None otherwise
        """
        for n in reversed(list(xpath.iter())):
            if n.tag == node.tag and n.attrib == node.attrib and n.text == node.text:
                return n
            # Find the node if it had been moved (only fields can be moved)
            if node.tag == 'field':  # Only fields are currently supported
                name = node.get('name')
                if n.get('position') == 'move' and name in moved_fields:
                    # the moved nodes are set as xpath so in order to match the
                    # nodes we need to compare both xpath
                    old_node = moved_fields.get(name)['old']
                    if n.get('expr') == self._node_to_xpath(old_node):
                        return n
        return None

    def _add_xpath_to_arch(self, arch, xpath):
            """
            Appends the xpath to the arch if the xpath's position != 'replace'
            (deletion), otherwise it is prepended to the arch.

            This is done because when moving an existing field somewhere before
            its original position it will append a replace xpath and then
            append the existing field xpath, effictively removing the one just
            added and showing the one that existed before.
            """
            # TODO: Only add attributes if the xpath has children
            if xpath.get('position') == 'replace':
                arch.insert(0, xpath)
            else:
                arch.append(xpath)

    def _clone_and_append_to(self, node, parent_node):
        """
        Clones the passed-in node and appends it to the passed-in
        parent_node

        Returns the parent_node with the newly-appended node
        """
        if node.tag is etree.Comment:
            # For comments, node.tag is the constructor of Comment nodes
            elem = parent_node.append(etree.Comment(node.text))
        else:
            # This doesn't copy the children, but we don't truly
            # care, since children will be another diff line
            elem = etree.SubElement(parent_node, node.tag, node.attrib)
            elem.text = node.text
            elem.tail = node.tail
        return elem

    def _node_to_xpath(self, target_node, node_context=None):
        """
        Creates and returns a relative xpath that points to target_node
        """
        if target_node.tag == 'attribute':
            target_node = target_node.getparent().getparent()
        elif target_node.tag == 'attributes':
            target_node = target_node.getparent()

        root = target_node.getroottree()
        el_name = target_node.get('name')

        if el_name and root.xpath('count(//*[@name="%s"])' % el_name) == 1:
            # there are cases when there are multiple instances of the same
            # named element in the same view, but for different reasons
            # i.e.: sub-views and kanban views
            expr = '//%s' % self._identify_node(target_node)
        else:
            ancestors = [
                self._identify_node(n, node_context)
                for n in target_node.iterancestors()
                if n.getparent() is not None
            ]
            node = self._identify_node(target_node, node_context)
            if ancestors:
                expr = '//%s/%s' % ('/'.join(reversed(ancestors)), node)
            else:
                # There are cases where there might not be any ancestors
                # like in a brand new gantt or calendar view, if that's the
                # case then just give the identified node
                expr = '//%s' % node

        return expr

    def _identify_node(self, node, node_context=None):
        """
        Creates and returns an identifier for the passed-in node either by using
        its name attribute (relative identifier) or by getting the number of preceding
        sibling elements (absolute identifier)
        """
        # Some nodes may have a name which is not id-like, but is a technical attribute
        # that won't be unique
        named_tags = ['field', 'button']

        # 0. Identify "regular" nodes by their name: name here is id-like
        if node.get('name') and node.tag not in named_tags:
            node_str = '%s[@name=\'%s\']' % (node.tag, node.get('name'))
            return node_str

        same_tag_prev_siblings = list(node.itersiblings(tag=node.tag, preceding=True))

        # Otherwise, we'd have to compute the absolute path of the node along 2 cases
        # 1. Current node does not have a name or doesn't need one
        if not node.get('name') or node.tag not in named_tags:
            # Only consider same tag siblings that don't have a name either
            colliding_prev_siblings = [
                sibling for sibling in same_tag_prev_siblings
                if ('name' not in sibling.attrib)
            ]

            node_str = '%s' % (node.tag,)

            # Only count no name node to avoid conflict with other studio change
            if len(colliding_prev_siblings) != len(same_tag_prev_siblings):
                node_str += '[not(@name)]'

            # We need to add 1 to the number of previous siblings to get the
            # position index of the node because these indices start at 1 in an xpath context.
            node_str += '[%s]' % (len(colliding_prev_siblings) + 1,)
            return node_str

        # 2. Current node has a name which is not id-like
        # There can be more than one node in that case
        if node.get('name') and node.tag in named_tags:
            # Only consider same tag siblings that do have the same name
            colliding_prev_siblings = [
                sibling for sibling in same_tag_prev_siblings
                if (node.get('name') == sibling.get('name'))
            ]

            node_str = '%s[@name=\'%s\']' % (
                node.tag,
                node.get('name'),
            )
            if len(colliding_prev_siblings):
                node_str += '[%s]' % (len(colliding_prev_siblings) + 1,)

            return node_str

    def _closest_node_to_xpath(self, node, old_view, moved_fields, node_context=None):
        """
        Returns an expr and position for the node closest to the passed-in node so
        that it may be used as a target.

        The closest node will be one adjacent to this one and that has an identifiable
        name (name attr), this can be it's next sibling, previous sibling or its parent.

        If none is found, the method will fallback to next/previous sibling or parent even if they
        don't have an identifiable name, in which case an absolute xpath expr will be generated
        """

        def _is_valid_anchor(target_node):
            if (target_node is None) or not isinstance(target_node.tag, str):
                return None
            if target_node.tag in ['attribute', 'attributes']:
                return None
            if target_node.tag == 'field' and target_node.get('name') in moved_fields:
                # a moved field cannot be used as anchor
                return None
            target_node_expr = '.' + self._node_to_xpath(target_node, node_context)
            return bool(old_view.xpath(target_node_expr))

        nxt = node.getnext()
        prev = node.getprevious()

        if node.tag == 'attribute':
            # Invisible element
            target_node = node.getparent().getparent()  # /node/attributes/attribute
            reanchor_position = 'attributes'
        elif node.tag == 'page':
            # a page is always put inside its corresponding notebook
            target_node = node.getparent()
            reanchor_position = 'inside'
        else:
            # Visible element
            while prev is not None or nxt is not None:
                # Try to anchor onto the closest adjacent element
                if _is_valid_anchor(prev):
                    target_node = prev
                    reanchor_position = 'after'
                    break
                elif _is_valid_anchor(nxt):
                    target_node = nxt
                    reanchor_position = 'before'
                    break
                else:
                    if prev is not None:
                        prev = prev.getprevious()
                    if nxt is not None:
                        nxt = nxt.getnext()
            else:
                # Reanchor on first parent, but the "inside" will make it last child
                target_node = node.getparent()
                reanchor_position = 'inside'

        reanchor_expr = self._node_to_xpath(target_node, node_context)
        return reanchor_expr, reanchor_position

    def _stringify_view(self, arch, moved_fields=None):
        return self._stringify_node('', arch, moved_fields)

    def _stringify_node(self, ancestor, node, moved_fields=None):
        """
        Converts a node into its string representation

        Example:
            from: <field name='color'/>
              to: "/field[@name='color']\n"

        Returns the stringified node
        """
        result = ''
        node_string = ancestor + '/'
        if node.tag is etree.Comment:
            node_string += 'comment'
        else:
            node_string += node.tag

        if node.get('name') and node.get('name').strip():
            node_string += '[@name=%s]' % node.get('name').strip().replace('\n', ' ')
        if node.text and node.text.strip():
            node_string += '[@text=%s]' % node.text.strip().replace('\n', ' ')
        if node.tail and node.tail.strip():
            node_string += '[@tail=%s]' % node.tail.strip().replace('\n', ' ')
        if node.tag == 'field' and moved_fields and node.get('name') in moved_fields:
            # make sure we don't tagged fields which are not really moved
            # (i.e. if the field appears more than once in the view)
            if self._node_to_xpath(node) == self._node_to_xpath(moved_fields[node.get('name')]['new']):
                # ensure that moved fields do appear in the final diff
                # (if they don't, it's not possible to reconstruct `move` xpaths)
                node_string += '[@moved]'
        result += node_string + '\n'

        self._generate_node_attributes(node)
        for child in node.iterchildren():
            result += self._stringify_node(node_string, child, moved_fields)

        # have a end marker so same location changes are not mixed
        result += node_string + '[@closed]' + '\n'

        return result

    def _generate_node_attributes(self, node):
        """
        Generates attributes wrapper elements for each of the node's
        attributes and prepend them as first children of the node
        """
        if node.tag not in ('attribute', 'attributes'):
            # node.items() gives a list of tuples, each tuple representing
            # a key, value pair for attributes
            node_attributes = sorted(node.items(), key=lambda i: i[0], reverse=True)  # inverse alphabetically sort attributes by name
            if len(node_attributes):
                for attr in node_attributes:
                    attributes = etree.Element('attributes', {
                        'name': attr[0],
                    })
                    etree.SubElement(attributes, 'attribute', {
                        'name': attr[0],
                    }).text = attr[1]
                    node.insert(0, attributes)

    def _indent_tree(self, elem, level=0):
        """
        The lxml library doesn't pretty_print xml tails, this method aims
        to solve this.

        Returns the elem with properly indented text and tail
        """
        # See: http://lxml.de/FAQ.html#why-doesn-t-the-pretty-print-option-reformat-my-xml-output
        # Below code is inspired by http://effbot.org/zone/element-lib.htm#prettyprint
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for subelem in elem:
                self._indent_tree(subelem, level + 1)
            if not subelem.tail or not subelem.tail.strip():
                subelem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i
        return elem

    def copy_qweb_template(self):
        new = self.copy()
        new.inherit_id = False

        domain = [
            ('type', '=', 'qweb'),
            ('key', '!=', new.key),
            ('key', 'like', '%s_copy_%%' % new.key),
            ('key', 'not like', '%s_copy_%%_copy_%%' % new.key)]
        old_copies = self.search_read(domain, order='key desc')
        nos = [int(old_copy.get('key').split('_copy_').pop()) for old_copy in old_copies]
        copy_no = (nos and max(nos) or 0) + 1
        new_key = '%s_copy_%s' % (new.key, copy_no)

        cloned_templates = self.env.context.get('cloned_templates', {})
        self = self.with_context(cloned_templates=cloned_templates)
        cloned_templates[new.key] = new_key

        arch_tree = etree.fromstring(self._read_template(self.id))

        for node in arch_tree.findall(".//t[@t-call]"):
            tcall = node.get('t-call')
            if '{' in tcall:
                continue
            if tcall in self.TEMPLATE_VIEWS_BLACKLIST:
                continue
            if tcall not in cloned_templates:
                callview = self.search([('type', '=', 'qweb'), ('key', '=', tcall)], limit=1)
                if not callview:
                    raise UserError(_("Template '%s' not found") % tcall)
                callview.copy_qweb_template()
            node.set('t-call', cloned_templates[tcall])

        subtree = arch_tree.xpath("//*[@t-name]")
        if subtree:
            subtree[0].set('t-name', new_key)
            arch_tree = subtree[0]

        # copy translation from view combinations
        combined_views = self.browse()
        views_to_process = [self]
        while views_to_process:
            view = views_to_process.pop()
            if not view or view in combined_views:
                continue
            combined_views += view
            views_to_process += view.inherit_id
            views_to_process += view.get_inheriting_views_arch(view.model)
        fields_to_ignore = (field for field in self._fields if field != 'arch_base')
        for view in (combined_views - self).with_context(from_copy_translation=True):
            view.copy_translations(new, fields_to_ignore)

        new.write({
            'name': '%s copy(%s)' % (new.name, copy_no),
            'key': new_key,
            'arch_base': etree.tostring(arch_tree, encoding='unicode'),
        })

        return new

    # validation stuff
    def _validate_tag_button(self, node, name_manager, node_info):
        super()._validate_tag_button(node, name_manager, node_info)
        studio_approval = node.get('studio_approval')
        if studio_approval and self.type != 'form':
            self.handle_view_error(_("studio_approval attribute can only be set in form views"))
        if studio_approval and studio_approval not in ['True', 'False']:
            self.handle_view_error(_("Invalid studio_approval %s in button") % studio_approval)
