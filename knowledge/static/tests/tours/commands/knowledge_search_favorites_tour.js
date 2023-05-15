/** @odoo-module */

import { registry } from "@web/core/registry";
import { openCommandBar } from "../knowledge_tour_utils.js";
import { stepUtils } from "@web_tour/tour_service/tour_utils";

/**
 * Insert the Knowledge kanban view as an embedded view in article.
 *
 * @param {String} article article name
 * @returns {Array} steps
 */
const embedKnowledgeKanbanViewSteps = function (article) {
    return [{ // open the Knowledge App
        trigger: ".o_app[data-menu-xmlid='knowledge.knowledge_menu_root']",
    }, { // click on the search menu
        trigger: "[role='menuitem']:contains(Search)",
    }, { // toggle on the kanban view
        trigger: ".o_switch_view.o_kanban",
    }, { // wait for the kanban view
        trigger: ".o_kanban_renderer",
        run: () => {},
    }, { // open action menu dropdown
        trigger: ".o_control_panel .o_cp_action_menus button",
    }, { // click on the knowledge menu button
        trigger: ".o_control_panel .o_cp_action_menus .dropdown-toggle:contains(Knowledge)",
        run: function () {
            this.$anchor[0].dispatchEvent(new Event("mouseenter"));
        },
    }, { // click on insert view in article
        trigger: ".o_cp_action_menus span:contains('Insert view in article')",
    }, { // embed in article
        trigger: `.modal-dialog td.o_field_cell:contains(${article})`,
    }];
};

/**
 * Test favorite filters and use by default filters in embedded views in
 * Knowledge. Need an article with 2 named kanban embeds to work.
 *
 * @param {String} kanban1 name of the first kanban
 * @param {String} kanban2 name of the second kanban
 * @returns {Array} steps
 */
const validateFavoriteFiltersSteps = function (kanban1, kanban2) {
    return [{
        content: 'Open the search panel menu',
        trigger: `.o_knowledge_embedded_view:contains(${kanban1}) .o_control_panel .o_searchview_dropdown_toggler`,
    }, {
        trigger: ".o_favorite_menu .o_add_favorite",
    }, {
        trigger: ".o_favorite_menu:contains(Favorites) input[type='text']",
        run: "text testFilter",
    }, {
        // use by default
        trigger: ".o_favorite_menu .o-checkbox:contains(Default filter) input",
    }, {
        trigger: ".o_favorite_menu .o_save_favorite",
    },
    stepUtils.toggleHomeMenu(),
    {
        // open the Knowledge App
        trigger: ".o_app[data-menu-xmlid='knowledge.knowledge_menu_root']",
    }, {
        // check that the search item has been added
        trigger: ".o_facet_value",
        run: function () {
            const items = document.querySelectorAll(".o_facet_value");
            if (items.length !== 1) {
                console.error("The search should be applied only on the first view");
            } else if (items[0].innerText !== 'testFilter') {
                console.error(`Wrong favorite name: ${items[0].innerText}`);
            }
        },
    }, {
        // Open the favorite of the second kanban and check it has no favorite
        // (favorite are defined per view)
        trigger: `.o_breadcrumb:contains('${kanban2}')`,
        run: function () {
            const view = this.$anchor[0].closest(
                '.o_kanban_view'
            );
            const searchMenuButton = view.querySelector(".o_searchview_dropdown_toggler");
            searchMenuButton.click();
        },
    }, {
        trigger: ".o_favorite_menu",
        run: function () {
            const items = document.querySelectorAll(".o_favorite_menu .dropdown-item");
            if (items.length !== 1 || items[0].innerText !== "Save current search") {
                console.error("The favorite should not be available for the second view");
            }
        },
    }];
};

registry.category("web_tour.tours").add("knowledge_items_search_favorites_tour", {
    url: "/web",
    test: true,
    steps: [
        stepUtils.showAppsMenuItem(),
        {
            // open the Knowledge App
            trigger: ".o_app[data-menu-xmlid='knowledge.knowledge_menu_root']",
        },
        {
            trigger: ".o_field_html",
            run: function () {
                const header = document.querySelector(".o_breadcrumb_article_name input");
                if (header.value !== "Article 1") {
                    console.error(`Wrong article: ${header.value}`);
                }
            },
        },
        // Create the first Kanban
        {
            trigger: ".odoo-editor-editable > h1",
            run: function () {
                openCommandBar(this.$anchor[0]);
            },
        },
        {
            trigger: ".oe-powerbox-commandName:contains('Item Kanban')",
        },
        {
            trigger: ".modal-body input.form-control",
            run: "text Items 1",
        },
        {
            trigger: "button:contains('Insert')",
        },
        // Create the second Kanban
        {
            trigger: ".odoo-editor-editable > h1",
            run: function () {
                openCommandBar(this.$anchor[0]);
            },
        },
        {
            trigger: ".oe-powerbox-commandName:contains('Item Kanban')",
        },
        {
            trigger: ".modal-body input.form-control",
            run: "text Items 2",
        },
        {
            trigger: "button:contains('Insert')",
        },
        {
            trigger: "span:contains('Items 2')", // wait for kanban 2 to be inserted,
            run: () => {},
        },
        ...validateFavoriteFiltersSteps("Items 1", "Items 2"),
    ],
});

registry.category("web_tour.tours").add("knowledge_search_favorites_tour", {
    url: "/web",
    test: true,
    steps: [stepUtils.showAppsMenuItem(),
        // insert a first kanban view
        ...embedKnowledgeKanbanViewSteps("Article 1"),
        { // wait for embedded view to load and click on rename button
            trigger: '.o_knowledge_behavior_type_embedded_view:contains(Articles) .o_knowledge_toolbar button:contains(Rename)',
            allowInvisible: true,
        }, { // rename the view Kanban 1
            trigger: '.modal-dialog input.form-control',
            run: `text Kanban 1`,
        }, { // click on rename
            trigger: "button:contains('Rename')",
        },
        stepUtils.toggleHomeMenu(),
        // insert a second kanban view
        ...embedKnowledgeKanbanViewSteps("Article 1"),
        { // wait for embedded view to load
            trigger: '.o_knowledge_behavior_type_embedded_view:contains(Articles)',
        },
        ...validateFavoriteFiltersSteps("Kanban 1", "Articles"),
    ],
});