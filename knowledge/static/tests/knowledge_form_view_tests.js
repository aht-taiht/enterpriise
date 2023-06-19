/** @odoo-module */

import { ArticlesStructureBehavior } from "@knowledge/components/behaviors/articles_structure_behavior/articles_structure_behavior";
import { TableOfContentBehavior } from "@knowledge/components/behaviors/table_of_content_behavior/table_of_content_behavior";
import { click, getFixture, makeDeferred, nextTick } from "@web/../tests/helpers/utils";
import { patch, unpatch } from "@web/core/utils/patch";
import { makeView, setupViewRegistries } from "@web/../tests/views/helpers";
import { onMounted } from "@odoo/owl";
import { qweb as QWeb } from "web.core";
import { parseHTML } from "@web_editor/js/editor/odoo-editor/src/utils/utils";

const articlesStructureSearch = {
    records: [
        { id: 1, display_name: 'My Article', parent_id: false },
        { id: 2, display_name: 'Child 1', parent_id: [1, 'My Article'] },
        { id: 3, display_name: 'Child 2', parent_id: [1, 'My Article'] },
    ]
};

const articlesIndexSearch = {
    records: articlesStructureSearch.records.concat([
        { id: 4, display_name: 'Grand-child 1', parent_id: [2, 'Child 1'] },
        { id: 5, display_name: 'Grand-child 2', parent_id: [2, 'Child 1'] },
        { id: 6, display_name: 'Grand-child 3', parent_id: [3, 'Child 2'] },
    ])
};

/**
 * Insert an article structure (index or outline) in the target node. This will
 * guarantee that the structure behavior is fully mounted before continuing.
 * @param {HTMLElement} editable
 * @param {HTMLElement} target
 * @param {boolean} childrenOnly
 */
const insertArticlesStructure = async (editable, target, childrenOnly) => {
    const articleStructureMounted = makeDeferred();
    const wysiwyg = $(editable).data('wysiwyg');
    patch(ArticlesStructureBehavior.prototype, 'ARTICLE_STRUCTURE_PATCH_TEST', {
        setup() {
            this._super(...arguments);
            onMounted(() => {
                articleStructureMounted.resolve();
                unpatch(ArticlesStructureBehavior.prototype, 'ARTICLE_STRUCTURE_PATCH_TEST');
            });
        }
    });
    const selection = document.getSelection();
    selection.removeAllRanges();
    const range = new Range();
    range.setStart(target, 0);
    range.setEnd(target, 0);
    selection.addRange(range);
    await nextTick();
    wysiwyg._insertArticlesStructure(childrenOnly);
    await articleStructureMounted;
    await nextTick();
};

let fixture;
let type;
let resModel;
let serverData;
let arch;

QUnit.module("Knowledge - Articles Structure Command", (hooks) => {
    hooks.beforeEach(() => {
        fixture = getFixture();
        type = "form";
        resModel = "knowledge_article";
        serverData = {
            models: {
                knowledge_article: {
                    fields: {
                        display_name: {string: "Displayed name", type: "char"},
                        body: {string: "Body", type: 'html'},
                    },
                    records: [{
                        id: 1,
                        display_name: "My Article",
                        body: '<p class="test_target"><br/></p>',
                    }],
                    methods: {
                        get_sidebar_articles() {
                            return {articles: [], favorite_ids: []};
                        }
                    }
                }
            }
        };
        arch = '<form js_class="knowledge_article_view_form">' +
            '<sheet>' +
                '<div class="o_knowledge_editor">' +
                    '<field name="body" widget="html"/>' +
                '</div>' +
            '</sheet>' +
        '</form>';
        setupViewRegistries();
    });
    QUnit.test('Check Articles Structure is correctly built', async function (assert) {
        assert.expect(3);

        await makeView({
            type,
            resModel,
            serverData,
            arch,
            resId: 1,
            mockRPC(route, args) {
                if (route === '/web/dataset/search_read' && args.model === 'knowledge.article') {
                    return Promise.resolve(articlesStructureSearch);
                }
            }
        });

        const editable = fixture.querySelector('.odoo-editor-editable');
        const target = editable.querySelector('p.test_target');
        await insertArticlesStructure(editable, target, true);

        // /articles_structure only considers the direct children - "Child 1" and "Child 2"
        assert.containsN(editable, '.o_knowledge_articles_structure_content ol a', 2);
        assert.containsOnce(editable, '.o_knowledge_articles_structure_content ol a:contains("Child 1")');
        assert.containsOnce(editable, '.o_knowledge_articles_structure_content ol a:contains("Child 2")');
    });
    QUnit.test('Check Articles Index is correctly built - and updated', async function (assert) {
        assert.expect(8);

        let searchReadCallCount = 0;
        await makeView({
            type,
            resModel,
            serverData,
            arch,
            resId: 1,
            mockRPC(route, args) {
                if (route === '/web/dataset/search_read' && args.model === 'knowledge.article') {
                    if (searchReadCallCount === 0) {
                        searchReadCallCount++;
                        return Promise.resolve(articlesIndexSearch);
                    } else {
                        // return updated result (called when clicking on the refresh button)
                        return Promise.resolve({
                            records: articlesIndexSearch.records.concat([
                                { id: 7, display_name: 'Grand-child 4', parent_id: [3, 'Child 2'] },
                            ])
                        });
                    }
                }
            }
        });

        const editable = fixture.querySelector('.odoo-editor-editable');
        const target = editable.querySelector('p.test_target');
        await insertArticlesStructure(editable, target, false);

        // /articles_index considers whole children - "Child 1" and "Child 2" and then their respective children
        assert.containsN(editable, '.o_knowledge_articles_structure_content ol a', 5);
        assert.containsOnce(editable, '.o_knowledge_articles_structure_content ol a:contains("Child 1")');
        assert.containsOnce(editable, '.o_knowledge_articles_structure_content ol a:contains("Child 2")');
        assert.containsOnce(editable,
            '.o_knowledge_articles_structure_content ol:contains("Child 1") ol a:contains("Grand-child 1")');
        assert.containsOnce(editable,
            '.o_knowledge_articles_structure_content ol:contains("Child 1") ol a:contains("Grand-child 2")');
        assert.containsOnce(editable,
            '.o_knowledge_articles_structure_content ol:contains("Child 2") ol a:contains("Grand-child 3")');

        // clicking on update yields an additional Grand-child (see 'mockRPC' here above)
        // make sure our structure is correctly updated
        await click(editable, '.o_knowledge_behavior_type_articles_structure button[title="Update"]');
        await nextTick();

        assert.containsN(editable, '.o_knowledge_articles_structure_content ol a', 6);
        assert.containsOnce(editable,
            '.o_knowledge_articles_structure_content ol:contains("Child 2") ol a:contains("Grand-child 4")');

    });
});

//==============================================================================
//                                External Views
//==============================================================================

/**
 * Insert an "External" view inside knowledge article.
 * @param {HTMLElement} editable
 */
const testAppendBehavior = async (editable) => {
    const wysiwyg = $(editable).data('wysiwyg');

    const insertedDiv = parseHTML(QWeb.render('knowledge.abstract_behavior', {
        behaviorType: "o_knowledge_behavior_type_template",
    })).firstChild;
    wysiwyg.appendBehaviorBlueprint(insertedDiv);
    await nextTick();
};

QUnit.module("Knowledge - External View Insertion", (hooks) => {
    hooks.beforeEach(() => {
        fixture = getFixture();
        type = "form";
        resModel = "knowledge_article";
        serverData = {
            models: {
                knowledge_article: {
                    fields: {
                        display_name: {string: "Displayed name", type: "char"},
                        body: {string: "Body", type: 'html'},
                    },
                    records: [{
                        id: 1,
                        display_name: "Insertion Article",
                        body: '\n<p>\n<br/>\n</p>\n',
                    }],
                    methods: {
                        get_sidebar_articles() {
                            return {articles: [], favorite_ids: []};
                        }
                    }
                }
            }
        };
        arch = '<form js_class="knowledge_article_view_form">' +
            '<sheet>' +
                '<div class="o_knowledge_editor">' +
                    '<field name="body" widget="html"/>' +
                '</div>' +
            '</sheet>' +
        '</form>';
        setupViewRegistries();
    });
    QUnit.test('Check that the insertion of views goes as expected', async function (assert) {

        await makeView({
            type,
            resModel,
            serverData,
            arch,
            resId: 1
        });

        const editable = fixture.querySelector('.odoo-editor-editable');
        await testAppendBehavior(editable);

        // We are checking if the anchor has been correctly inserted inside
        // the article.
        assert.containsOnce(editable, '.o_knowledge_behavior_anchor');
        const anchor = editable.querySelector('.o_knowledge_behavior_anchor');
        assert.notOk(anchor.nextSiblingElement, 'The inserted view should be the last element in the article');
    });
});

//==============================================================================
//                                Table of Contents
//==============================================================================

/**
 * Insert a Table Of Content (TOC) in the target node. This will guarantee that
 * the TOC behavior is fully mounted before continuing.
 * @param {HTMLElement} editable - Root HTMLElement of the editor
 * @param {HTMLElement} target - Target node
 */
const insertTableOfContent = async (editable, target) => {
    const tocMounted = makeDeferred();
    const wysiwyg = $(editable).data('wysiwyg');
    patch(TableOfContentBehavior.prototype, 'TOC_PATCH_TEST', {
        setup() {
            this._super(...arguments);
            onMounted(() => {
                tocMounted.resolve();
                unpatch(TableOfContentBehavior.prototype, 'TOC_PATCH_TEST');
            });
        }
    });
    const selection = document.getSelection();
    selection.removeAllRanges();
    const range = new Range();
    range.setStart(target, 0);
    range.setEnd(target, 0);
    selection.addRange(range);
    await nextTick();
    wysiwyg._insertTableOfContent();
    await tocMounted;
    await nextTick();
};

/**
 * @param {Object} assert - QUnit assert object used to trigger asserts and exceptions
 * @param {HTMLElement} editable - Root HTMLElement of the editor
 * @param {Array[Object]} expectedHeadings - List of headings that should appear in the toc of the editable
 */
const assertHeadings = (assert, editable, expectedHeadings) => {
    const allHeadings = Array.from(editable.querySelectorAll('a.o_knowledge_toc_link'));
    for (let index = 0; index < expectedHeadings.length; index++) {
        const { title, depth } = expectedHeadings[index];
        const headingSelector = `a:contains("${title}").o_knowledge_toc_link_depth_${depth}`;
        // we have the heading in the DOM
        assert.containsOnce(editable, headingSelector);

        const $headingEl = $(editable).find(headingSelector);
        // it has the correct index (as item order is important)
        assert.equal(index, allHeadings.indexOf($headingEl[0]));
    }
};

QUnit.module("Knowledge Table of Content", (hooks) => {
    hooks.beforeEach(() => {
        fixture = getFixture();
        type = "form";
        resModel = "knowledge_article";
        serverData = {
            models: {
                knowledge_article: {
                    fields: {
                        display_name: {string: "Displayed name", type: "char"},
                        body: {string: "Body", type: 'html'},
                    },
                    records: [{
                        id: 1,
                        display_name: "My Article",
                        body: '<p class="test_target"><br/></p>' +
                        '<h1>Main 1</h1>' +
                            '<h2>Sub 1-1</h2>' +
                                '<h3>Sub 1-1-1</h3>' +
                                '<h3>Sub 1-1-2</h3>' +
                            '<h2>Sub 1-2</h2>' +
                                '<h3>Sub 1-2-1</h3>' +
                        '<h1>Main 2</h1>' +
                            '<h3>Sub 2-1</h3>' +
                            '<h3>Sub 2-2</h3>' +
                                '<h4>Sub 2-2-1</h4>' +
                                    '<h5>Sub 2-2-1-1</h5>' +
                            '<h3>Sub 2-3</h3>',
                    }, {
                        id: 2,
                        display_name: "My Article",
                        body: '<p class="test_target"><br/></p>' +
                        '<h2>Main 1</h2>' +
                            '<h3>Sub 1-1</h3>' +
                                '<h4>Sub 1-1-1</h4>' +
                                '<h4>Sub 1-1-2</h4>' +
                        '<h1>Main 2</h1>' +
                            '<h2>Sub 2-1</h2>',
                    }, {
                        id: 3,
                        display_name: "My Article",
                        body: `<p class="test_target"><br/></p>
                        <h3>Main 1</h3>
                        <h2>Main 2</h2>`,
                    }],
                    methods: {
                        get_sidebar_articles() {
                            return {articles: [], favorite_ids: []};
                        }
                    },
                },
            }
        };
        arch = '<form js_class="knowledge_article_view_form">' +
            '<sheet>' +
                '<div class="o_knowledge_editor d-flex flex-grow-1">' +
                    '<field name="body" widget="html"/>' +
                '</div>' +
            '</sheet>' +
        '</form>';
        setupViewRegistries();
    });
    QUnit.test("Check Table of Content is correctly built", async function (assert) {
        assert.expect(24);

        await makeView({
            type,
            resModel,
            serverData,
            arch,
            resId: 1,
        });

        const editable = fixture.querySelector('.odoo-editor-editable');
        const target = editable.querySelector('p.test_target');
        await insertTableOfContent(editable, target);

        const expectedHeadings = [
            {title: 'Main 1',      depth: 0},
            {title: 'Sub 1-1',     depth: 1},
            {title: 'Sub 1-1-1',   depth: 2},
            {title: 'Sub 1-1-2',   depth: 2},
            {title: 'Sub 1-2',     depth: 1},
            {title: 'Sub 1-2-1',   depth: 2},
            {title: 'Main 2',      depth: 0},
            // the next <h3>'s should be at depth 1, because we don't have any <h2> in this subtree
            {title: 'Sub 2-1',     depth: 1},
            {title: 'Sub 2-2',     depth: 1},
            {title: 'Sub 2-2-1',   depth: 2},
            {title: 'Sub 2-2-1-1', depth: 3},
            // the next <h3> should be at depth 1, because we don't have any <h2> in this subtree
            {title: 'Sub 2-3',     depth: 1},
        ];

        assertHeadings(assert, editable, expectedHeadings);
    });

    QUnit.test('Check Table of Content is correctly built - starting with H2', async function (assert) {
        assert.expect(12);

        await makeView({
            type,
            resModel,
            serverData,
            arch,
            resId: 2,
        });

        const editable = fixture.querySelector('.odoo-editor-editable');
        const target = editable.querySelector('p.test_target');
        await insertTableOfContent(editable, target);

        const expectedHeadings = [
            // The "Main 1" section is a <h2>, but it should still be at depth 0
            // as there is no <h1> above it
            {title: 'Main 1',      depth: 0},
            {title: 'Sub 1-1',     depth: 1},
            {title: 'Sub 1-1-1',   depth: 2},
            {title: 'Sub 1-1-2',   depth: 2},
            {title: 'Main 2',      depth: 0},
            {title: 'Sub 2-1',     depth: 1},
        ];
        assertHeadings(assert, editable, expectedHeadings);
    });

    QUnit.test('Check Table of Content is correctly built - starting with H3 followed by H2', async function (assert) {
        assert.expect(4);

        await makeView({
            type,
            resModel,
            serverData,
            arch,
            resId: 3,
        });

        const editable = fixture.querySelector('.odoo-editor-editable');
        const target = editable.querySelector('p.test_target');
        await insertTableOfContent(editable, target);

        const expectedHeadings = [
            // The "Main 1" section is a <h3> at depth 0, and the next "Main 2" section
            // is  <h2>, which should still be at the 0 depth instead of 1
            {title: 'Main 1',      depth: 0},
            {title: 'Main 2',      depth: 0},
        ];
        assertHeadings(assert, editable, expectedHeadings);
    });
});