/** @odoo-module */

import { browser } from "@web/core/browser/browser";
import {
    click,
    getFixture,
    nextTick,
    patchWithCleanup,
    editInput,
    dragAndDrop,
    drag,
} from "@web/../tests/helpers/utils";
import {
    createViewEditor,
    registerViewEditorDependencies,
    createMockViewResult,
    editAnySelect,
    disableHookAnimation,
    selectorContains,
} from "@web_studio/../tests/client_action/view_editors/view_editor_tests_utils";

import { ImageField } from "@web/views/fields/image/image_field";
import { createEnterpriseWebClient } from "@web_enterprise/../tests/helpers";
import { doAction } from "@web/../tests/webclient/helpers";
import { openStudio, registerStudioDependencies } from "../../helpers";
import { fakeCommandService } from "@web/../tests/helpers/mock_services";
import { registry } from "@web/core/registry";
import { makeArchChanger } from "./view_editor_tests_utils";
import { start, startServer } from "@mail/../tests/helpers/test_utils";
import { registerCleanup } from "@web/../tests/helpers/cleanup";
import { RPCError } from "@web/core/network/rpc_service";
import { setupMessagingServiceRegistries } from "@mail/../tests/helpers/webclient_setup";
import { EventBus } from "@odoo/owl";
import { fieldService } from "@web/core/field_service";

/** @type {Node} */
let target;
let serverData;

function currentSidebarTab() {
    return target.querySelector(".o_web_studio_sidebar .nav-link.active").innerText;
}

const fakeMultiTab = {
    start() {
        const bus = new EventBus();
        return {
            bus,
            get currentTabId() {
                return null;
            },
            isOnMainTab() {
                return true;
            },
            getSharedValue(key, defaultValue) {
                return "";
            },
            setSharedValue(key, value) {},
            removeSharedValue(key) {},
        };
    },
};

const fakeImStatusService = {
    start() {
        return {
            registerToImStatus() {},
            unregisterFromImStatus() {},
        };
    },
};

function getFormEditorServerData() {
    return {
        models: {
            coucou: {
                fields: {
                    id: { string: "Id", type: "integer" },
                    display_name: { string: "Name", type: "char" },
                    m2o: { string: "Product", type: "many2one", relation: "product" },
                    char_field: { type: "char", string: "A char" },
                },
                records: [
                    {
                        id: 1,
                        display_name: "Kikou petite perruche",
                        m2o: 1,
                    },
                    {
                        id: 2,
                        display_name: "Coucou Two",
                    },
                ],
            },
            product: {
                fields: {
                    id: { string: "Id", type: "integer" },
                    display_name: { string: "Name", type: "char" },
                },
                records: [
                    {
                        id: 1,
                        display_name: "A very good product",
                    },
                ],
            },
            partner: {
                fields: {
                    id: { string: "Id", type: "integer" },
                    display_name: { string: "Name", type: "char" },
                    image: { string: "Image", type: "binary" },
                },
                records: [
                    {
                        id: 1,
                        display_name: "jean",
                        image: {},
                    },
                ],
            },
        },
    };
}

QUnit.module("View Editors", (hooks) => {
    hooks.beforeEach(() => {
        serverData = getFormEditorServerData();
        registerViewEditorDependencies();
        patchWithCleanup(browser, {
            setTimeout: (fn) => fn(),
        });
        target = getFixture();

        registry.category("services").add("multi_tab", fakeMultiTab, { force: true });
        registry.category("services").add("im_status", fakeImStatusService, { force: true });
    });
    QUnit.module("Form");

    QUnit.test(
        "Form editor should contains the view and the editor sidebar",
        async function (assert) {
            await createViewEditor({
                serverData,
                type: "form",
                resModel: "coucou",
                arch: /*xml*/ `
                        <form>
                            <sheet>
                                <field name="name"/>
                            </sheet>
                        </form>
                    `,
            });

            assert.containsOnce(
                target,
                ".o_web_studio_editor_manager .o_web_studio_view_renderer",
                "There should be one view renderer"
            );
            assert.containsOnce(
                target,
                ".o_web_studio_editor_manager .o_web_studio_sidebar",
                "There should be one sidebar"
            );
        }
    );

    QUnit.test("empty form editor", async function (assert) {
        assert.expect(3);

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: "<form/>",
        });

        assert.containsOnce(
            target,
            ".o_web_studio_form_view_editor",
            "there should be a form editor"
        );
        assert.containsNone(
            target,
            ".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable",
            "there should be no node"
        );
        assert.containsNone(
            target,
            ".o_web_studio_form_view_editor .o_web_studio_hook",
            "there should be no hook"
        );
    });

    QUnit.test("optional field not in form editor", async function (assert) {
        assert.expect(1);

        await createViewEditor({
            serverData,
            type: "form",
            arch: `
                    <form>
                        <sheet>
                            <field name="display_name"/>
                        </sheet>
                    </form>`,
            resModel: "coucou",
        });

        await click(target, ".o_web_studio_view_renderer .o_field_char", true);
        assert.containsNone(
            target,
            ".o_web_studio_sidebar_optional_select",
            "there shouldn't be an optional field"
        );
    });

    QUnit.test("many2one field edition", async function (assert) {
        assert.expect(3);

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: `
                    <form>
                        <sheet>
                            <field name="m2o"/>
                        </sheet>
                    </form>
                `,
            resId: 1,
            mockRPC: function (route, args) {
                if (route === "/web_studio/get_studio_view_arch") {
                    return { studio_view_arch: "" };
                }
                if (route === "/web_studio/edit_view") {
                    return {};
                }
                if (route === "/web_studio/edit_view_arch") {
                    return {};
                }
                if (args.method === "get_formview_action") {
                    throw new Error("The many2one form view should not be opened");
                }
            },
        });

        assert.containsOnce(
            target,
            ".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable",
            "there should be one node"
        );

        // edit the many2one
        await click(
            target,
            ".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable",
            true
        );
        await nextTick();

        assert.ok(
            target.querySelectorAll(".o_web_studio_sidebar .o_web_studio_property").length > 0,
            "the sidebar should now display the field properties"
        );

        // TODO: Adapt to new studio
        // assert.containsOnce(target, '.o_web_studio_sidebar select[name="widget"] option[value="selection"]',
        //     "the widget in selection should be supported in m2o");
        assert.hasClass(
            target.querySelector(
                ".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable"
            ),
            "o-web-studio-editor--element-clicked",
            "the column should have the clicked style"
        );
    });

    QUnit.test("image field edition (change size)", async function (assert) {
        assert.expect(9);

        const arch = `
                <form>
                    <sheet>
                        <field name='image' widget='image' options='{"size":[0, 90],"preview_image":"coucou"}'/>
                    </sheet>
                </form>
            `;

        patchWithCleanup(ImageField.prototype, {
            setup() {
                this._super();
                owl.onMounted(() => {
                    assert.step(
                        `image, width: ${this.props.width}, height: ${this.props.height}, previewImage: ${this.props.previewImage}`
                    );
                });
            },
        });

        await createViewEditor({
            serverData,
            resModel: "partner",
            arch: arch,
            resId: 1,
            type: "form",
            mockRPC: {
                "/web_studio/edit_view": () => {
                    assert.step("edit_view");
                    const newArch = `
                            <form>
                                <sheet>
                                    <field name='image' widget='image' options='{"size":[0, 270],"preview_image":"coucou"}'/>
                                </sheet>
                            </form>
                        `;
                    return createMockViewResult(serverData, "form", newArch, "partner");
                },
            },
        });

        assert.containsOnce(
            target,
            ".o_web_studio_form_view_editor .o_field_image",
            "there should be one image"
        );
        assert.verifySteps(
            ["image, width: undefined, height: 90, previewImage: coucou"],
            "the image should have been fetched"
        );

        // edit the image
        await click(target, ".o_web_studio_form_view_editor .o_field_image", true);

        assert.containsOnce(
            target,
            ".o_web_studio_property_size",
            "the sidebar should display dropdown to change image size"
        );

        assert.strictEqual(
            target.querySelector(".o_web_studio_property_size .text-start").textContent,
            "Small",
            "The image size should be correctly selected"
        );
        assert.hasClass(
            target.querySelector(".o_web_studio_form_view_editor .o_field_image"),
            "o-web-studio-editor--element-clicked",
            "image should have the clicked style"
        );

        // change image size to large
        await editAnySelect(
            target,
            ".o_web_studio_sidebar .o_web_studio_property_size .o_select_menu",
            "Large"
        );
        assert.verifySteps(
            ["edit_view", "image, width: undefined, height: 270, previewImage: coucou"],
            "the image should have been fetched again"
        );
    });

    QUnit.test("signature field edition (change full_name)", async function (assert) {
        assert.expect(8);

        const arch = `
                <form>
                    <group>
                        <field name='display_name'/>
                        <field name='m2o'/>
                    </group>
                </form>
            `;

        let editViewCount = 0;
        let newFieldName;

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: arch,
            resId: 1,
            mockRPC: function (route, args) {
                if (route === "/web_studio/edit_view") {
                    editViewCount++;
                    let newArch;
                    if (editViewCount === 1) {
                        assert.strictEqual(
                            args.operations[0].node.attrs.widget,
                            "signature",
                            "'signature' widget should be there on field being dropped"
                        );
                        newFieldName = args.operations[0].node.field_description.name;
                        newArch =
                            "<form>" +
                            "<group>" +
                            "<field name='display_name'/>" +
                            "<field name='m2o'/>" +
                            "<field name='" +
                            newFieldName +
                            "' widget='signature'/>" +
                            "</group>" +
                            "</form>";
                        serverData.models.coucou.fields[newFieldName] = {
                            string: "Signature",
                            type: "binary",
                        };
                    } else if (editViewCount === 2) {
                        assert.strictEqual(
                            args.operations[1].new_attrs.options,
                            '{"full_name":"display_name"}',
                            "correct options for 'signature' widget should be passed"
                        );
                        newArch =
                            "<form>" +
                            "<group>" +
                            "<field name='display_name'/>" +
                            "<field name='m2o'/>" +
                            "<field name='" +
                            newFieldName +
                            "' widget='signature' options='{\"full_name\": \"display_name\"}'/>" +
                            "</group>" +
                            "</form>";
                    } else if (editViewCount === 3) {
                        assert.strictEqual(
                            args.operations[2].new_attrs.options,
                            '{"full_name":"m2o"}',
                            "correct options for 'signature' widget should be passed"
                        );
                        newArch =
                            "<form>" +
                            "<group>" +
                            "<field name='display_name'/>" +
                            "<field name='m2o'/>" +
                            "<field name='" +
                            newFieldName +
                            "' widget='signature' options='{\"full_name\": \"m2o\"}'/>" +
                            "</group>" +
                            "</form>";
                    }
                    return createMockViewResult(serverData, "form", newArch, "coucou");
                }
            },
        });

        // drag and drop the new signature field
        disableHookAnimation(target);
        await dragAndDrop(
            ".o_web_studio_new_fields .o_web_studio_field_signature",
            ".o_inner_group .o_web_studio_hook:first-child"
        );

        assert.containsOnce(
            target,
            ".o_web_studio_form_view_editor .o_signature",
            "there should be one signature field"
        );

        // edit the signature
        await click(target.querySelector(".o_web_studio_form_view_editor .o_signature"));

        assert.containsOnce(
            target,
            ".o_web_studio_property_full_name .o-dropdown",
            "the sidebar should display dropdown to change 'Auto-complete with' field"
        );
        assert.strictEqual(
            target.querySelector(".o_web_studio_property_full_name button").textContent,
            "",
            "the auto complete field should be empty by default"
        );

        await editAnySelect(target, ".o_web_studio_property_full_name .o_select_menu", "Name");

        assert.strictEqual(
            target.querySelector(".o_web_studio_property_full_name button").textContent,
            "Name",
            "the auto complete field should be correctly selected"
        );

        // change auto complete field to 'm2o'
        await editAnySelect(target, ".o_web_studio_property_full_name .o_select_menu", "Product");

        assert.strictEqual(
            target.querySelector(".o_web_studio_property_full_name button").textContent,
            "Product",
            "the auto complete field should be correctly selected"
        );
    });

    QUnit.test("integer field should come with 0 as default value", async function (assert) {
        // The arch has a full blown group because the formEditor prevents dropping new Integer fields in a simpler arch
        const arch = `
                <form>
                    <group>
                        <field name='display_name'/>
                    </group>
                </form>`;
        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: arch,
            mockRPC: (route, args) => {
                if (route === "/web_studio/edit_view") {
                    assert.step("edit_view");
                    assert.strictEqual(args.operations[0].node.field_description.type, "integer");
                    assert.strictEqual(
                        args.operations[0].node.field_description.default_value,
                        "0"
                    );
                }
            },
        });

        disableHookAnimation(target);
        await dragAndDrop(
            target.querySelector(".o_web_studio_new_fields .o_web_studio_field_integer"),
            target.querySelector(".o_web_studio_hook")
        );
        assert.verifySteps(["edit_view"]);
    });

    QUnit.test("invisible form editor", async function (assert) {
        assert.expect(6);

        const arch = `
                <form>
                    <sheet>
                        <field name='display_name' invisible='1'/>
                        <group>
                            <field name='m2o' attrs="{'invisible': [('id', '!=', '42')]}"/>
                        </group>
                    </sheet>
                </form>
            `;

        await createViewEditor({
            type: "form",
            serverData,
            resModel: "coucou",
            arch,
        });

        serverData.views = {
            "coucou,false,form": arch,
        };

        assert.containsNone(target, ".o_web_studio_form_view_editor .o_field_widget");
        assert.containsOnce(
            target,
            ".o_web_studio_form_view_editor .o-web-studio-editor--element-clickable",
            "the invisible node should not be editable (only the group has a node-id set)"
        );
        assert.containsN(
            target,
            ".o_web_studio_form_view_editor .o_web_studio_hook",
            2,
            "there should be two hooks (outside and inside the group"
        );

        // click on show invisible
        await click(target, ".o_web_studio_sidebar li:nth-child(2) a");
        await nextTick();
        await click(target, ".o_web_studio_sidebar input#show_invisible");
        await nextTick();

        assert.containsN(
            target,
            ".o_web_studio_form_view_editor .o_web_studio_show_invisible",
            2,
            "there should be one visible nodes (the invisible ones)"
        );
        assert.containsNone(
            target,
            ".o_web_studio_form_view_editor .o_invisible_modifier",
            "there should be no invisible node"
        );
        assert.containsN(
            target,
            ".o_web_studio_form_view_editor .o_web_studio_hook",
            3,
            "there should be three hooks"
        );
    });

    QUnit.test("form editor - chatter edition", async function (assert) {
        assert.expect(5);
        const pyEnv = await startServer();
        setupMessagingServiceRegistries({ serverData: pyEnv.getData() });

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: `
                    <form>
                        <sheet>
                            <field name='display_name'/>
                        </sheet>
                        <div class='oe_chatter'/>
                    </form>
                `,
            mockRPC: {
                "/web_studio/get_email_alias": () => Promise.resolve({ email_alias: "coucou" }),
            },
        });

        assert.containsOnce(
            target,
            ".o_web_studio_form_view_editor .o-mail-Form-chatter",
            "there should be a chatter node"
        );

        // click on the chatter
        await click(
            target,
            ".o_web_studio_form_view_editor .o-mail-Form-chatter .o_web_studio_overlay",
            true
        );
        await nextTick();

        assert.strictEqual(
            currentSidebarTab(),
            "Properties",
            "the Properties tab should now be active"
        );

        assert.containsOnce(
            target,
            '.o_web_studio_sidebar input[name="email_alias"]',
            "the sidebar should now display the chatter properties"
        );
        assert.strictEqual(
            target.querySelector('.o_web_studio_sidebar input[name="email_alias"]').value,
            "coucou",
            "the email alias in sidebar should be fetched"
        );
        assert.hasClass(
            target.querySelector(".o_web_studio_form_view_editor .o-mail-Form-chatter"),
            "o-web-studio-editor--element-clicked",
            "the chatter should have the clicked style"
        );
    });

    QUnit.test(
        "fields without value and label (outside of groups) are shown in form",
        async function (assert) {
            assert.expect(6);

            await createViewEditor({
                serverData,
                resModel: "coucou",
                type: "form",
                arch: `
                        <form>
                            <sheet>
                                <group>
                                    <field name='id'/>
                                    <field name='m2o'/>
                                </group>
                                <field name='display_name'/>
                                <field name='char_field'/>
                            </sheet>
                        </form>
                    `,
                resId: 2,
                mockRPC: {},
            });

            assert.doesNotHaveClass(
                target.querySelector('.o_web_studio_form_view_editor [name="id"]'),
                "o_web_studio_widget_empty",
                "the id field should not have the widget empty class"
            );
            assert.doesNotHaveClass(
                target.querySelector('.o_web_studio_form_view_editor [name="m2o"]'),
                "o_web_studio_widget_empty",
                "the m2o field should not have the widget_empty class"
            );

            assert.hasClass(
                target.querySelector('.o_web_studio_form_view_editor [name="m2o"]'),
                "o_field_empty",
                "the m2o field is empty and therefore should have the o_field_empty class"
            );
            assert.doesNotHaveClass(
                target.querySelector('.o_web_studio_form_view_editor [name="display_name"]'),
                "o_web_studio_widget_empty",
                "the display_name field should not have the o_web_studio_widget_empty class"
            );

            assert.hasClass(
                target.querySelector('.o_web_studio_form_view_editor [name="char_field"]'),
                "o_web_studio_widget_empty",
                "the char_field should have the o_web_studio_widget_empty class"
            );
            assert.strictEqual(
                target.querySelector('.o_web_studio_form_view_editor [name="char_field"]')
                    .innerText,
                "A char",
                "The text in the empty char field should be 'A char'"
            );
        }
    );

    QUnit.test("invisible group in form sheet", async function (assert) {
        assert.expect(8);

        const arch = `<form>
                <sheet>
                    <group>
                        <group class="kikou" string="Kikou" modifiers="{&quot;invisible&quot;: true}"/>
                        <group class="kikou2" string='Kikou2'/>
                    </group>
                </sheet>
            </form>`;

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: `<form>
                        <sheet>
                            <group>
                                <group class="kikou" string='Kikou'/>
                                <group class="kikou2" string='Kikou2'/>
                            </group>
                        </sheet>
                    </form>`,
            mockRPC: {
                "/web_studio/edit_view": (route, args) => {
                    assert.equal(
                        args.operations[0].new_attrs.invisible,
                        1,
                        'we should send "invisible"'
                    );
                    return createMockViewResult(serverData, "form", arch, "coucou");
                },
            },
        });

        assert.containsN(target, ".o_inner_group", 2, "there should be two groups");

        await click(target, ".o_inner_group:first-child");
        await nextTick();
        assert.containsOnce(
            target,
            ".o_web_studio_property input#invisible",
            "should have invisible checkbox"
        );

        assert.ok(
            target.querySelector(".o_web_studio_sidebar .o_web_studio_property input#invisible")
                .checked === false,
            "invisible checkbox should not be checked"
        );

        await click(target, ".o_web_studio_sidebar .o_web_studio_property input#invisible");
        await nextTick();

        assert.containsN(
            target,
            ".o_inner_group",
            1,
            "there should be one visible group now, kikou group is not rendered"
        );

        assert.containsNone(target, ".o-web-studio-editor--element-clicked");
        assert.hasClass(
            target.querySelectorAll(".o_web_studio_sidebar.o_notebook .nav-item a")[0],
            "active"
        );

        await click(target.querySelector(".o_inner_group.kikou2"));
        await nextTick();

        const groupInput = target.querySelector(
            '.o_web_studio_sidebar .o_web_studio_sidebar_text input[name="string"]'
        );
        assert.strictEqual(groupInput.value, "Kikou2", "the group name in sidebar should be set");
    });

    QUnit.test("correctly display hook in form sheet", async function (assert) {
        assert.expect(11);

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: `
                <form>
                    <sheet>
                        <!-- hook here -->
                        <group>
                            <group/>
                            <group/>
                        </group>
                        <!-- hook here -->
                        <group>
                            <group/>
                            <group/>
                        </group>
                        <!-- hook here -->
                    </sheet>
                </form>`,
        });

        const sheetHooksValues = [
            {
                xpath: "/form[1]/sheet[1]",
                position: "inside",
                type: "insideSheet",
            },
            {
                xpath: "/form[1]/sheet[1]/group[1]",
                position: "after",
                type: "afterGroup",
            },
            {
                xpath: "/form[1]/sheet[1]/group[2]",
                position: "after",
                type: "afterGroup",
            },
        ];

        target.querySelectorAll(".o_form_sheet > div.o_web_studio_hook").forEach((hook) => {
            const control = sheetHooksValues.shift();
            assert.deepEqual(control, { ...hook.dataset });
        });

        assert.containsN(
            target,
            ".o_web_studio_form_view_editor .o_form_sheet > div.o_web_studio_hook",
            3,
            "there should be three hooks as children of the sheet"
        );

        const innerGroupsHooksValues = [
            {
                xpath: "/form[1]/sheet[1]/group[1]/group[1]",
                position: "inside",
            },
            {
                xpath: "/form[1]/sheet[1]/group[1]/group[2]",
                position: "inside",
            },
            {
                xpath: "/form[1]/sheet[1]/group[2]/group[1]",
                position: "inside",
            },
            {
                xpath: "/form[1]/sheet[1]/group[2]/group[2]",
                position: "inside",
            },
        ];

        target
            .querySelectorAll(".o_form_sheet .o_inner_group > div.o_web_studio_hook")
            .forEach((hook) => {
                const control = innerGroupsHooksValues.shift();
                assert.deepEqual(control, { ...hook.dataset });
            });

        assert.hasClass(
            target.querySelector(".o_web_studio_form_view_editor .o_form_sheet > div:nth-child(2)"),
            "o_web_studio_hook",
            "second div should be a hook"
        );
        assert.hasClass(
            target.querySelector(".o_web_studio_form_view_editor .o_form_sheet > div:nth-child(4)"),
            "o_web_studio_hook",
            "fourth div should be a hook"
        );
        assert.hasClass(
            target.querySelector(".o_web_studio_form_view_editor .o_form_sheet > div:nth-child(6)"),
            "o_web_studio_hook",
            "last div should be a hook"
        );
    });

    QUnit.test("correctly display hook below group title", async function (assert) {
        assert.expect(14);

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: `
                <form>
                    <sheet>
                        <group>
                            </group>
                            <group string='Kikou2'>
                            </group>
                        <group>
                            <field name='m2o'/>
                        </group>
                        <group string='Kikou'>
                            <field name='id'/>
                        </group>
                    </sheet>
                </form>`,
        });

        // first group (without title, without content)
        const firstGroup = target.querySelector(
            ".o_web_studio_form_view_editor .o_inner_group:nth-child(3)"
        );
        assert.containsOnce(
            firstGroup,
            ".o_web_studio_hook",
            "First group, there should be 1 hook"
        );
        assert.hasClass(
            firstGroup.querySelector(":scope > div:nth-child(1)"),
            "o_web_studio_hook",
            "First group, the first div should be a hook"
        );

        // second group (with title, without content)
        const secondGroup = target.querySelector(
            ".o_web_studio_form_view_editor .o_inner_group:nth-child(4)"
        );
        assert.containsOnce(
            secondGroup,
            ".o_web_studio_hook",
            "Second group, there should be 1 hook"
        );
        assert.strictEqual(
            secondGroup.querySelector(":scope > div:nth-child(1)").innerText.toUpperCase(),
            "KIKOU2",
            "Second group, the first div is the group title"
        );
        assert.hasClass(
            secondGroup.querySelector(":scope > div:nth-child(2)"),
            "o_web_studio_hook",
            "Second group, the second div should be a hook"
        );

        // third group (without title, with content)
        const thirdGroup = target.querySelector(
            ".o_web_studio_form_view_editor .o_inner_group:nth-child(5)"
        );
        assert.containsN(
            thirdGroup,
            ".o_web_studio_hook",
            2,
            "Third group, there should be 2 hooks"
        );
        assert.hasClass(
            thirdGroup.querySelector(":scope > div:nth-child(1)"),
            "o_web_studio_hook",
            "Third group, the first div should be a hook"
        );
        assert.strictEqual(
            thirdGroup.querySelector(":scope > div:nth-child(2)").innerText.toUpperCase(),
            "PRODUCT",
            "Third group, the second div is the field"
        );
        assert.containsOnce(
            thirdGroup,
            "div:nth-child(2) .o_web_studio_hook",
            "Third group, the hook should be placed after the field"
        );

        // last group (with title, with content)
        const lastGroup = target.querySelector(
            ".o_web_studio_form_view_editor .o_inner_group:nth-child(6)"
        );
        assert.containsN(lastGroup, ".o_web_studio_hook", 2, "Last group, there should be 2 hooks");
        assert.strictEqual(
            lastGroup.querySelector(":scope > div:nth-child(1)").innerText.toUpperCase(),
            "KIKOU",
            "Last group, the first div is the group title"
        );
        assert.hasClass(
            lastGroup.querySelector(":scope > div:nth-child(2)"),
            "o_web_studio_hook",
            "Last group, the second div should be a hook"
        );
        assert.strictEqual(
            lastGroup.querySelector(":scope > div:nth-child(3)").innerText.toUpperCase(),
            "ID",
            "Last group, the third div is the field"
        );
        assert.containsOnce(
            lastGroup,
            "div:nth-child(3) > .o_web_studio_hook",
            "Last group, the hook is after the field"
        );
    });

    QUnit.test("correctly display hook at the end of tabs -- empty group", async function (assert) {
        assert.expect(1);

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: `<form>
                        <sheet>
                            <notebook>
                                <page string='foo'>
                                <group></group>
                                </page>
                            </notebook>
                        </sheet>
                </form>`,
        });

        const childs = document.querySelector(
            ".o_web_studio_form_view_editor .o_notebook .tab-pane.active"
        ).children;

        assert.strictEqual(
            childs[childs.length - 1].classList.contains("o_web_studio_hook"),
            true,
            "When the page contains only an empty group, last child is a studio hook."
        );
    });

    QUnit.test(
        "correctly display hook at the end of tabs -- multiple groups with content and an empty group",
        async function (assert) {
            assert.expect(1);

            await createViewEditor({
                serverData,
                type: "form",
                resModel: "coucou",
                arch: `<form>
                        <sheet>
                            <notebook>
                                <page string="foo">
                                    <group>
                                        <field name="m2o"/>
                                    </group>
                                    <group>
                                        <field name="id"/>
                                    </group>
                                    <group></group>
                                </page>
                            </notebook>
                        </sheet>
                    </form>`,
            });

            const childs = document.querySelector(
                ".o_web_studio_form_view_editor .o_notebook .tab-pane.active"
            ).children;

            assert.strictEqual(
                childs[childs.length - 1].classList.contains("o_web_studio_hook"),
                true,
                "When the page contains multiple groups with content and an empty group, last child is still a studio hook."
            );
        }
    );

    QUnit.test("notebook page hooks", async (assert) => {
        const arch = `
                    <form>
                        <sheet>
                            <notebook>
                                <page string="field"><field name="display_name" /></page>
                                <page string="outer">
                                    <group><group></group></group>
                                </page>
                                <page string='foo'>
                                    <group>
                                        <field name='m2o'/>
                                    </group>
                                    <group>
                                        <field name='id'/>
                                    </group>
                                    <group></group>
                                </page>
                            </notebook>
                        </sheet>
                    </form>`;

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch,
        });

        assert.containsOnce(target, ".o_notebook .tab-pane.active > .o_web_studio_hook");

        assert.deepEqual(
            {
                ...target.querySelector(".o_notebook .tab-pane.active > .o_web_studio_hook")
                    .dataset,
            },
            {
                position: "inside",
                type: "page",
                xpath: "/form[1]/sheet[1]/notebook[1]/page[1]",
            }
        );
        await click(target.querySelectorAll(".o_notebook .nav-item a")[4]);
        assert.containsOnce(target, ".o_notebook .tab-pane.active > .o_web_studio_hook");

        assert.deepEqual(
            {
                ...target.querySelector(".o_notebook .tab-pane.active > .o_web_studio_hook")
                    .dataset,
            },
            {
                position: "after",
                type: "afterGroup",
                xpath: "/form[1]/sheet[1]/notebook[1]/page[2]/group[1]",
            }
        );

        await click(target.querySelectorAll(".o_notebook .nav-item a")[5]);
        assert.containsOnce(target, ".o_notebook .tab-pane.active > .o_web_studio_hook");
        assert.deepEqual(
            {
                ...target.querySelector(".o_notebook .tab-pane.active > .o_web_studio_hook")
                    .dataset,
            },
            {
                position: "inside",
                type: "page",
                xpath: "/form[1]/sheet[1]/notebook[1]/page[3]",
            }
        );
    });

    QUnit.test("notebook edition", async function (assert) {
        assert.expect(9);

        const arch = `
                <form>
                    <sheet>
                        <group>
                            <field name='display_name'/>
                        </group>
                        <notebook>
                            <page string='Kikou'>
                                <field name='id'/>
                            </page>
                        </notebook>
                    </sheet>
                </form>`;

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: arch,
            mockRPC: function (route, args) {
                if (route === "/web_studio/edit_view") {
                    assert.strictEqual(
                        args.operations[0].node.tag,
                        "page",
                        "a page should be added"
                    );
                    assert.strictEqual(
                        args.operations[0].node.attrs.string,
                        "New Page",
                        "the string attribute should be set"
                    );
                    assert.strictEqual(
                        args.operations[0].position,
                        "inside",
                        "a page should be added inside the notebook"
                    );
                    assert.strictEqual(
                        args.operations[0].target.tag,
                        "notebook",
                        "the target should be the notebook in edit_view"
                    );
                    return createMockViewResult(serverData, "form", arch, "coucou");
                }
            },
        });

        assert.containsN(
            target,
            ".o_content .o_notebook li",
            2,
            "there should be one existing page and a fake one"
        );

        // // click on existing tab
        const firstTab = target.querySelector(".o_content .o_notebook li");
        await click(firstTab);

        assert.hasClass(
            firstTab,
            "o-web-studio-editor--element-clicked",
            "the page should be clickable"
        );

        assert.containsN(
            target,
            ".o_web_studio_property",
            2,
            "the sidebar should now display the page properties"
        );

        assert.strictEqual(
            document.querySelector(".o_web_studio_property.o_web_studio_sidebar_text input").value,
            "Kikou",
            "the page name in sidebar should be set"
        );

        assert.containsOnce(
            target,
            ".o_limit_group_visibility",
            "the groups should be editable for notebook pages"
        );

        // add a new page
        await click(document.querySelectorAll(".o_content .o_notebook li")[1]);
    });

    QUnit.test("notebook with empty page", async (assert) => {
        assert.expect(3);

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: `<form>
                        <sheet>
                            <notebook>
                                <page string="field"></page>
                            </notebook>
                        </sheet>
                    </form>`,
        });

        await click(target.querySelector(".o_web_studio_view_renderer .o_notebook li"));
        assert.strictEqual(
            currentSidebarTab(),
            "Properties",
            "The sidebar should now display the properties tab"
        );
        assert.containsN(
            target,
            ".o_web_studio_property",
            2,
            "the sidebar should now display the page properties"
        );
        assert.strictEqual(
            target.querySelectorAll(".o_web_studio_property input")[1].value,
            "field",
            "the page label is correctly set"
        );
    });

    QUnit.test("invisible notebook page in form", async function (assert) {
        assert.expect(9);

        const arch = `
            <form>
                <sheet>
                    <notebook>
                        <page class="kikou" string='Kikou' modifiers="{&quot;invisible&quot;: true}">
                            <field name='id'/>
                        </page>
                        <page class="kikou2" string='Kikou2'>
                            <field name='char_field'/>
                        </page>
                    </notebook>
                </sheet>
            </form>`;

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: `<form>
                        <sheet>
                            <notebook>
                                <page class="kikou" string='Kikou'>
                                    <field name='id'/>
                                </page>
                                <page class="kikou2" string='Kikou2'>
                                    <field name='char_field'/>
                                </page>
                            </notebook>
                        </sheet>
                    </form>`,
            mockRPC: function (route, args) {
                if (route === "/web_studio/edit_view") {
                    assert.equal(
                        args.operations[0].new_attrs.invisible,
                        1,
                        'we should send "invisible"'
                    );
                    return createMockViewResult(serverData, "form", arch, "coucou");
                }
            },
        });

        assert.containsN(
            target,
            ".o_web_studio_view_renderer .o_notebook li.o-web-studio-editor--element-clickable",
            2,
            "there should be two pages"
        );

        await click(target.querySelector(".o_web_studio_view_renderer .o_notebook li"));
        assert.containsOnce(
            target,
            ".o_web_studio_sidebar input#invisible",
            "should have invisible checkbox"
        );
        const invisibleCheckbox = target.querySelector(".o_web_studio_sidebar input#invisible");
        assert.strictEqual(
            invisibleCheckbox.checked,
            false,
            "invisible checkbox should not be checked"
        );

        await click(invisibleCheckbox);
        await nextTick();
        assert.containsN(
            target,
            ".o_web_studio_view_renderer .o_notebook li",
            2,
            "there should be one visible page and a fake one"
        );
        assert.isNotVisible(
            target.querySelector(".o_notebook li .kikou"),
            "there should be an invisible page"
        );

        assert.containsNone(target, ".o-web-studio-editor--element-clicked");

        assert.strictEqual(currentSidebarTab(), "Add");

        await click(target.querySelector("li .kikou2"));
        assert.strictEqual(
            target.querySelector(".o_web_studio_property.o_web_studio_sidebar_text input").value,
            "Kikou2",
            "the page name in sidebar should be set"
        );
    });

    QUnit.test("label edition", async function (assert) {
        assert.expect(10);

        const arch = `
            <form>
                <sheet>
                    <group>
                        <label for='display_name' string='Kikou'/>
                        <div><field name='display_name' nolabel='1'/></div>
                        <field name="char_field"/>
                    </group>
                </sheet>
            </form>`;
        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: arch,
            mockRPC: function (route, args) {
                if (route === "/web_studio/edit_view") {
                    assert.deepEqual(
                        args.operations[0].target,
                        {
                            tag: "label",
                            attrs: {
                                for: "display_name",
                            },
                            xpath_info: [
                                {
                                    indice: 1,
                                    tag: "form",
                                },
                                {
                                    indice: 1,
                                    tag: "sheet",
                                },
                                {
                                    indice: 1,
                                    tag: "group",
                                },
                                {
                                    indice: 1,
                                    tag: "label",
                                },
                            ],
                        },
                        "the target should be set in edit_view"
                    );
                    assert.deepEqual(
                        args.operations[0].new_attrs,
                        { string: "Yeah" },
                        "the string attribute should be set in edit_view"
                    );
                    return createMockViewResult(serverData, "form", arch, "coucou");
                }
            },
        });

        const label = document.querySelector(".o_web_studio_form_view_editor label");
        assert.strictEqual(label.innerText, "Kikou", "the label should be correctly set");
        await click(label);

        assert.hasClass(
            label,
            "o-web-studio-editor--element-clicked",
            "the label should be clicked"
        );

        assert.containsOnce(
            target,
            ".o_web_studio_property",
            "the sidebar should now display the label properties"
        );

        const sidebarlabel = document.querySelector(".o_web_studio_sidebar_text input");
        assert.strictEqual(sidebarlabel.value, "Kikou", "the label name in sidebar should be set");

        editInput(document, ".o_web_studio_sidebar_text input", "Yeah");

        const charFieldLabel = document.querySelectorAll("label.o_form_label")[1];
        assert.strictEqual(
            charFieldLabel.innerText,
            "A char",
            "The second label should be 'A char'"
        );

        await click(charFieldLabel);

        assert.doesNotHaveClass(
            label,
            "o-web-studio-editor--element-clicked",
            "the field label should not be clicked"
        );

        assert.containsN(
            target,
            ".o_web_studio_property",
            7,
            "the sidebar should now display the field properties"
        );

        const charFieldSidebarLabel = document.querySelector(".o_web_studio_sidebar_text input");
        assert.strictEqual(
            charFieldSidebarLabel.value,
            "A char",
            "the label name in sidebar should be set"
        );
    });

    QUnit.test("add a statusbar", async function (assert) {
        assert.expect(8);

        const arch = `
            <form>
                <sheet>
                    <group><field name='display_name'/></group>
                </sheet>
            </form>`;

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: arch,
            mockRPC(route, args) {
                if (route === "/web_studio/edit_view") {
                    assert.strictEqual(
                        args.operations.length,
                        2,
                        "there should be 2 operations (one for statusbar and one for the new field"
                    );
                    assert.deepEqual(args.operations[0], { type: "statusbar" });
                    assert.deepEqual(
                        args.operations[1].target,
                        { tag: "header" },
                        "the target should be correctly set"
                    );
                    assert.strictEqual(
                        args.operations[1].position,
                        "inside",
                        "the position should be correctly set"
                    );
                    assert.deepEqual(
                        args.operations[1].node.attrs,
                        { widget: "statusbar", options: "{'clickable': '1'}" },
                        "the options should be correctly set"
                    );
                }
            },
        });

        const statusbar = target.querySelector(
            ".o_web_studio_form_view_editor .o_web_studio_statusbar_hook"
        );
        assert.containsOnce(
            target,
            ".o_web_studio_form_view_editor .o_web_studio_statusbar_hook",
            "there should be a hook to add a statusbar"
        );

        await click(statusbar);
        assert.containsOnce(target, ".o_dialog .modal", "there should be one modal");
        assert.containsN(
            target,
            ".o_dialog .o_web_studio_selection_editor li.o-draggable .o-web-studio-interactive-list-item-label",
            3,
            "there should be 3 pre-filled values for the selection field"
        );
        await click(target.querySelector(".modal-footer .btn-primary"));
    });

    QUnit.test("move a field in form", async function (assert) {
        assert.expect(3);
        const arch = `<form>
                <sheet>
                    <group>
                        <field name='display_name'/>
                        <field name='char_field'/>
                        <field name='m2o'/>
                    </group>
                </sheet>
            </form>`;

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: arch,
            mockRPC: function (route, args) {
                if (route === "/web_studio/edit_view") {
                    assert.deepEqual(
                        args.operations[0],
                        {
                            node: {
                                tag: "field",
                                attrs: { name: "m2o" },
                            },
                            position: "before",
                            target: {
                                tag: "field",
                                xpath_info: [
                                    {
                                        indice: 1,
                                        tag: "form",
                                    },
                                    {
                                        indice: 1,
                                        tag: "sheet",
                                    },
                                    {
                                        indice: 1,
                                        tag: "group",
                                    },
                                    {
                                        indice: 1,
                                        tag: "field",
                                    },
                                ],
                                attrs: { name: "display_name" },
                            },
                            type: "move",
                        },
                        "the move operation should be correct"
                    );
                    // the server sends the arch in string but it's post-processed
                    // by the ViewEditorManager
                    const arch =
                        "<form>" +
                        "<sheet>" +
                        "<group>" +
                        "<field name='m2o'/>" +
                        "<field name='display_name'/>" +
                        "<field name='char_field'/>" +
                        "</group>" +
                        "</sheet>" +
                        "</form>";
                    return createMockViewResult(serverData, "form", arch, "coucou");
                }
            },
        });

        assert.strictEqual(
            target.querySelector(".o_web_studio_form_view_editor .o_form_sheet").innerText,
            "Name\nA char\nProduct",
            "The initial ordering of the fields must be correct"
        );

        // Don't be bothered by transition effects
        disableHookAnimation(target);
        // move m2o before display_name
        await dragAndDrop(
            ".o-draggable[data-field-name='m2o']",
            ".o_inner_group .o_web_studio_hook"
        );
        assert.strictEqual(
            target.querySelector(".o_web_studio_form_view_editor .o_form_sheet").innerText,
            "Product\nName\nA char",
            "The ordering of the fields after the dragAndDrop should be correct"
        );
    });

    QUnit.test("form editor add avatar image", async function (assert) {
        assert.expect(15);
        const arch = `<form>
                <sheet>
                    <div class='oe_title'>
                        <field name='name'/>
                    </div>
                </sheet>
            </form>`;
        let editViewCount = 0;

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "partner",
            arch: arch,
            mockRPC: function (route, args) {
                if (route === "/web_studio/edit_view") {
                    editViewCount++;
                    let newArch;
                    if (editViewCount === 1) {
                        assert.deepEqual(
                            args.operations[0],
                            {
                                field: "image",
                                type: "avatar_image",
                            },
                            "Proper field name and operation type should be passed"
                        );
                        newArch = `<form>
                                <sheet>
                                    <field name='image' widget='image' class='oe_avatar' options='{"preview_image": "image"}'/>
                                    <div class='oe_title'>
                                        <field name='name'/>
                                    </div>
                                </sheet>
                            </form>`;
                    } else if (editViewCount === 2) {
                        assert.deepEqual(
                            args.operations[1],
                            {
                                type: "remove",
                                target: {
                                    tag: "field",
                                    attrs: {
                                        name: "image",
                                        class: "oe_avatar",
                                    },
                                    xpath_info: [
                                        {
                                            indice: 1,
                                            tag: "form",
                                        },
                                        {
                                            indice: 1,
                                            tag: "sheet",
                                        },
                                        {
                                            indice: 1,
                                            tag: "field",
                                        },
                                    ],
                                },
                            },
                            "Proper field name and operation type should be passed"
                        );
                        newArch = arch;
                    } else if (editViewCount === 3) {
                        assert.deepEqual(
                            args.operations[2],
                            {
                                field: "",
                                type: "avatar_image",
                            },
                            "Proper field name and operation type should be passed"
                        );
                        serverData.models.partner.fields["x_avatar_image"] = {
                            string: "Image",
                            type: "binary",
                        };
                        newArch = `<form>
                                <sheet>
                                    <field name='x_avatar_image' widget='image' class='oe_avatar' options='{"preview_image": "x_avatar_image"}'/>
                                    <div class='oe_title'>
                                        <field name='name'/>
                                    </div>
                                </sheet>
                            </form>`;
                    }
                    //serverData, arch, model
                    return createMockViewResult(serverData, "form", newArch, "partner");
                }
            },
        });

        assert.containsNone(
            target,
            ".o_field_widget.oe_avatar",
            "there should be no avatar image field"
        );

        assert.containsOnce(
            target,
            ".oe_avatar.o_web_studio_avatar",
            "there should be the hook for avatar image"
        );

        // Test with existing field.
        await click(target.querySelector(".oe_avatar.o_web_studio_avatar"));
        await nextTick();

        assert.containsN(
            target,
            ".modal .modal-body select > option",
            2,
            "there should be two option Field selection drop-down "
        );

        assert.containsOnce(
            target,
            ".modal .modal-body select > option[value='image']",
            "there should be 'Image' option with proper value set in Field selection drop-down"
        );

        // add existing image field
        await editAnySelect(target, "select[name='field']", "image");

        // Click 'Confirm' Button
        await click(target.querySelector(".modal .modal-footer .btn-primary"));
        assert.containsOnce(
            target,
            '.o_field_widget.oe_avatar[name="image"]',
            "there should be avatar image with field image"
        );
        assert.containsNone(
            target,
            ".oe_avatar.o_web_studio_avatar",
            "the avatar image hook should not be there"
        );

        // Remove already added field from view to test new image field case.
        await click(target.querySelector(".oe_avatar"));
        await click(target.querySelector(".o_web_studio_sidebar .o_web_studio_remove"));
        assert.strictEqual(
            target.querySelector(".modal-body").innerText,
            "Are you sure you want to remove this field from the view?",
            "dialog should display the correct message"
        );
        await click(target.querySelector(".modal-footer .btn-primary"));
        assert.containsNone(
            target,
            ".o_field_widget.oe_avatar",
            "there should be no avatar image field"
        );
        assert.containsOnce(
            target,
            ".oe_avatar.o_web_studio_avatar",
            "there should be the hook for avatar image"
        );

        // Test with new field.
        await click(target.querySelector(".oe_avatar.o_web_studio_avatar"));
        assert.containsOnce(
            target,
            ".modal .modal-body select > option.o_new",
            "there should be 'New Field' option in Field selection drop-down"
        );
        // add new image field
        await editAnySelect(target, "select[name='field']", "");
        // Click 'Confirm' Button
        await click(target.querySelector(".modal .modal-footer .btn-primary"));
        assert.containsOnce(
            target,
            '.o_field_widget.oe_avatar[name="x_avatar_image"]',
            "there should be avatar image with field name x_avatar_image"
        );
        assert.containsNone(
            target,
            ".oe_avatar.o_web_studio_avatar",
            "there should be no hook for avatar image"
        );
    });

    QUnit.test("sidebar for a related field", async function (assert) {
        serverData.models.product.fields.related = {
            type: "char",
            related: "partner.display_name",
            string: "myRelatedField",
        };
        const arch = `<form>
                <sheet>
                    <div class='oe_title'>
                        <field name='related'/>
                    </div>
                </sheet>
            </form>`;

        await createViewEditor({
            serverData,
            type: "form",
            resModel: "product",
            arch: arch,
        });

        const fieldTarget = target.querySelector(".o_field_widget[name='related']");
        assert.hasClass(fieldTarget, "o_web_studio_widget_empty");
        assert.strictEqual(fieldTarget.textContent, "myRelatedField");
        await click(fieldTarget);
        assert.strictEqual(
            target.querySelector(".o_web_studio_sidebar .nav-link.active").textContent,
            "Properties"
        );
        assert.strictEqual(target.querySelector("input[name='string']").value, "myRelatedField");
    });

    QUnit.test("Phone field in form with SMS", async function (assert) {
        serverData.models.coucou.fields.display_name.string = "Display Name";
        const arch = `
        <form><sheet>
            <group>
                <field name='display_name' widget='phone' />
            </group>
        </sheet></form>`;
        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: arch,
            mockRPC(route, args) {
                if (route === "/web_studio/edit_view") {
                    assert.step("edit_view");
                    assert.deepEqual(args.operations[0].node.attrs, {
                        name: "display_name",
                        widget: "phone",
                    });
                    assert.deepEqual(args.operations[0].new_attrs, {
                        options: '{"enable_sms":false}',
                    });
                }
            },
        });

        await click(selectorContains(target, ".o_form_label", "Display Name"));
        assert.containsOnce(
            target,
            '.o_web_studio_sidebar input[id="enable_sms"]:checked',
            "By default the boolean should be true"
        );
        await click(target.querySelector('.o_web_studio_sidebar input[id="enable_sms"]'));
        assert.verifySteps(["edit_view"]);
    });

    QUnit.test("modification of field appearing multiple times in view", async function (assert) {
        // the typical case of the same field in a single view is conditional sub-views
        // that use attrs={'invisible': [domain]}
        // if the targeted node is after a hidden view, the hidden one should be ignored / skipped
        const arch = `<form>
            <group invisible="1">
                <field name="display_name"/>
            </group>
            <group>
                <field name="display_name"/>
            </group>
            <group>
                <field name="char_field" />
            </group>
        </form>`;

        await createViewEditor({
            serverData,
            type: "form",
            arch: arch,
            resModel: "coucou",
            mockRPC: function (route, args) {
                if (route === "/web_studio/edit_view") {
                    assert.step("edit_view");
                    assert.deepEqual(
                        args.operations[0].target.xpath_info,
                        [
                            {
                                tag: "form",
                                indice: 1,
                            },
                            {
                                tag: "group",
                                indice: 2,
                            },
                            {
                                tag: "field",
                                indice: 1,
                            },
                        ],
                        "the target should be the field of the second group"
                    );
                    assert.deepEqual(
                        args.operations[0].new_attrs,
                        { string: "Foo" },
                        "the string attribute should be changed from default to 'Foo'"
                    );
                }
            },
        });

        const visibleElement = target.querySelector(
            ".o_web_studio_form_view_editor .o_wrap_label.o-web-studio-editor--element-clickable"
        );
        assert.strictEqual(visibleElement.textContent, "Name", "the name should be correctly set");

        await click(visibleElement);
        const labelInput = target.querySelector('.o_web_studio_property input[name="string"]');
        assert.strictEqual(labelInput.value, "Name", "the name in the sidebar should be set");
        await editInput(labelInput, null, "Foo");
        assert.verifySteps(["edit_view"]);
    });

    QUnit.test("Open form view with button_box in studio", async function (assert) {
        assert.expect(1);

        const arch = `<form>
            <div name="button_box" class="oe_button_box" modifiers='{"invisible": [["display_name", "=", false]]}'>
                <button type="object" class="oe_stat_button" icon="fa-check-square">
                    <field name="display_name"/>
                </button>
            </div>
        </form>`;
        await createViewEditor({
            serverData,
            type: "form",
            arch: arch,
            resModel: "partner",
            resId: 1,
        });

        const buttonBoxFieldEl = target.querySelector(".oe_button_box button .o_field_widget span");
        assert.strictEqual(buttonBoxFieldEl.textContent, "jean", "there should be a button_box");
    });

    QUnit.test("new button in buttonbox", async function (assert) {
        assert.expect(6);
        patchWithCleanup(browser, { setTimeout: () => 1 });
        const arch = `<form><sheet><field name='display_name'/></sheet></form>`;
        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch,
            mockRPC(route, args) {
                if (args.method === "name_search") {
                    return [[1, " Test Field (Test)"]];
                }
                if (route === "/web_studio/edit_view") {
                    assert.deepEqual(args.operations, [
                        { type: "buttonbox" },
                        {
                            type: "add",
                            target: {
                                tag: "div",
                                attrs: {
                                    class: "oe_button_box",
                                },
                            },
                            position: "inside",
                            node: {
                                tag: "button",
                                field: 1,
                                string: "New button",
                                attrs: {
                                    class: "oe_stat_button",
                                    icon: "fa-diamond",
                                },
                            },
                        },
                    ]);
                    return createMockViewResult(serverData, "form", arch, "partner");
                }
            },
        });

        await click(target.querySelector(".o_web_studio_button_hook"));
        assert.containsOnce(target, ".o_dialog .modal", "there should be one modal");
        assert.containsOnce(
            target,
            ".o_dialog .o_input_dropdown .o-autocomplete",
            "there should be a many2one for the related field"
        );

        await click(target.querySelector(".modal-footer button:first-child"));
        assert.containsOnce(
            target,
            ".o_notification",
            "notification shown at confirm when no field selected"
        );
        assert.containsOnce(target, ".o_dialog .modal", "dialog is still present");

        await click(target.querySelector(".o-autocomplete--input"));
        await click(target.querySelector(".o-autocomplete .o-autocomplete--dropdown-item"));
        await click(target.querySelector(".modal-footer button:first-child"));
        assert.containsNone(target, ".o_dialog .modal", "should not display the create modal");
    });

    QUnit.test("new button in buttonbox with first element invisible", async function (assert) {
        serverData.models["coucou"].records[0] = {
            display_name: "someName",
            id: 99,
        };
        const arch = `
                <form>
                    <sheet>
                        <div class="oe_button_box" name="button_box">
                            <button name="someName" class="someClass" type="object"
                                modifiers="{&quot;invisible&quot;: [[&quot;display_name&quot;, &quot;=&quot;, &quot;someName&quot;]]}" />
                        </div>
                        <field name='display_name'/>
                    </sheet>
                </form>`;
        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: arch,
            resId: 99,
        });
        assert.containsOnce(target, ".oe_button_box .o_web_studio_button_hook");
        assert.containsNone(target, "button.someClass");
    });

    QUnit.test("element removal", async function (assert) {
        assert.expect(10);

        let editViewCount = 0;
        const arch = `<form><sheet>
                    <group>
                        <field name='display_name'/>
                        <field name='m2o'/>
                    </group>
                    <notebook><page name='page'><field name='id'/></page></notebook>
                </sheet></form>`;
        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: arch,
            mockRPC(route, args) {
                if (route === "/web_studio/edit_view") {
                    editViewCount++;
                    if (editViewCount === 1) {
                        assert.strictEqual(
                            _.has(args.operations[0].target, "xpath_info"),
                            true,
                            "should give xpath_info even if we have the tag identifier attributes"
                        );
                    } else if (editViewCount === 2) {
                        assert.strictEqual(
                            _.has(args.operations[1].target, "xpath_info"),
                            true,
                            "should give xpath_info even if we have the tag identifier attributes"
                        );
                    } else if (editViewCount === 3) {
                        assert.strictEqual(
                            args.operations[2].target.tag,
                            "group",
                            "should compute correctly the parent node for the group"
                        );
                    } else if (editViewCount === 4) {
                        assert.strictEqual(
                            args.operations[3].target.tag,
                            "notebook",
                            "should delete the notebook because the last page is deleted"
                        );
                        assert.strictEqual(
                            _.last(args.operations[3].target.xpath_info).tag,
                            "notebook",
                            "should have the notebook as xpath last element"
                        );
                    }
                    return createMockViewResult(serverData, "form", arch, "coucou");
                }
            },
        });
        // remove field
        await click(target.querySelector('[name="display_name"]').parentElement);
        await click(target.querySelector(".o_web_studio_sidebar .o_web_studio_remove"));
        assert.strictEqual(
            target.querySelector(".modal-body").textContent,
            "Are you sure you want to remove this field from the view?",
            "should display the correct message"
        );
        await click(target.querySelector(".modal .btn-primary"));

        // remove other field so group is empty
        await click(target.querySelector('[name="m2o"]').parentElement);
        await click(target.querySelector(".o_web_studio_sidebar .o_web_studio_remove"));
        assert.strictEqual(
            target.querySelector(".modal-body").textContent,
            "Are you sure you want to remove this field from the view?",
            "should display the correct message"
        );
        await click(target.querySelector(".modal .btn-primary"));

        // remove group
        await click(target.querySelector(".o_inner_group.o-web-studio-editor--element-clickable"));
        await click(target.querySelector(".o_web_studio_sidebar .o_web_studio_remove"));
        assert.strictEqual(
            target.querySelector(".modal-body").textContent,
            "Are you sure you want to remove this group from the view?",
            "should display the correct message"
        );
        await click(target.querySelector(".modal .btn-primary"));

        // remove page
        await click(target.querySelector(".o_notebook li.o-web-studio-editor--element-clickable"));
        await click(target.querySelector(".o_web_studio_sidebar .o_web_studio_remove"));
        assert.strictEqual(
            target.querySelector(".modal-body").textContent,
            "Are you sure you want to remove this page from the view?",
            "should display the correct message"
        );
        await click(target.querySelector(".modal .btn-primary"));
        assert.strictEqual(editViewCount, 4, "should have edit the view 4 times");
    });

    QUnit.test(
        "disable creation(no_create options) in many2many_tags widget",
        async function (assert) {
            serverData.models.product.fields.m2m = {
                string: "M2M",
                type: "many2many",
                relation: "product",
            };

            const arch = /*xml*/ `
            <form>
                <sheet>
                    <group>
                        <field name='display_name'/>
                        <field name='m2m' widget='many2many_tags'/>
                    </group>
                </sheet>
            </form>`;

            const mockRPC = (route, args) => {
                if (route === "/web_studio/edit_view") {
                    assert.step("edit_view");
                    assert.equal(
                        args.operations[0].new_attrs.options,
                        '{"no_create":true}',
                        "no_create options should send with true value"
                    );
                }
            };

            await createViewEditor({
                serverData,
                mockRPC,
                type: "form",
                arch,
                resModel: "product",
            });

            await click(
                target.querySelector(".o_web_studio_view_renderer .o_field_many2many_tags")
            );
            assert.containsOnce(
                target,
                ".o_web_studio_sidebar #no_create",
                "should have no_create option for m2m field"
            );
            assert.containsNone(
                target,
                ".o_web_studio_sidebar #no_create:checked",
                "by default the no_create option should be false"
            );

            await click(target.querySelector(".o_web_studio_sidebar #no_create"));
            assert.verifySteps(["edit_view"]);
        }
    );

    QUnit.test(
        "disable creation(no_create options) in many2many_tags_avatar widget",
        async function (assert) {
            serverData.models.product.fields.m2m = {
                string: "M2M",
                type: "many2many",
                relation: "product",
            };

            const arch = `
            <form>
                <sheet>
                    <group>
                    <field name="m2m" widget="many2many_tags_avatar"/>
                    </group>
                </sheet>
            </form>`;
            await createViewEditor({
                serverData,
                type: "form",
                resModel: "product",
                arch,
                mockRPC: function (route, args) {
                    if (route === "/web_studio/edit_view") {
                        assert.step("edit_view");
                        assert.equal(
                            args.operations[0].new_attrs.options,
                            '{"no_create":true}',
                            "no_create options should send with true value"
                        );
                    }
                },
            });

            await click(
                target.querySelector(".o_web_studio_view_renderer .o_field_many2many_tags_avatar")
            );
            assert.containsOnce(
                target,
                ".o_web_studio_sidebar #no_create",
                "should have no_create option for many2many_tags_avatar widget"
            );
            assert.containsNone(
                target,
                ".o_web_studio_sidebar #no_create:checked",
                "by default the no_create option should be false"
            );

            await click(target.querySelector(".o_web_studio_sidebar #no_create"));
            assert.verifySteps(["edit_view"]);
        }
    );

    QUnit.test(
        "disable creation(no_create options) in many2many_avatar_user and many2many_avatar_employee widget",
        async function (assert) {
            const pyEnv = await startServer();

            const mailModels = pyEnv.getData();
            mailModels.product.fields.m2m_users = {
                string: "M2M Users",
                type: "many2many",
                relation: "res.users",
            };
            mailModels.product.fields.m2m_employees = {
                string: "M2M Employees",
                type: "many2many",
                relation: "hr.employee.public",
            };

            Object.assign(serverData.models, mailModels);
            setupMessagingServiceRegistries({ serverData });

            const arch = /*xml*/ `
            <form>
                <sheet>
                    <group>
                    <field name="m2m_users" widget="many2many_avatar_user"/>
                    </group>
                </sheet>
            </form>`;

            const mockRPC = (route, args) => {
                if (route === "/web_studio/edit_view") {
                    assert.step("edit_view");
                    assert.equal(
                        args.operations[0].new_attrs.options,
                        '{"no_create":true}',
                        "no_create options should send with true value"
                    );
                }
            };

            registry.category("services").add("command", fakeCommandService);
            await createViewEditor({
                serverData,
                resModel: "product",
                type: "form",
                mockRPC,
                arch,
            });

            await click(
                target.querySelector(
                    '.o_web_studio_view_renderer .o_field_many2many_avatar_user[name="m2m_users"]'
                )
            );
            assert.containsOnce(
                target,
                ".o_web_studio_sidebar #no_create",
                "should have no_create option for many2many_avatar_user"
            );
            assert.containsNone(
                target,
                ".o_web_studio_sidebar #no_create:checked",
                "by default the no_create option should be false"
            );

            await click(target.querySelector(".o_web_studio_sidebar #no_create"));
            assert.verifySteps(["edit_view"]);
        }
    );

    QUnit.test("notebook and group drag and drop after a group", async function (assert) {
        assert.expect(2);
        const arch = `<form><sheet>
            <group>
            <field name='display_name'/>
            </group>
        </sheet></form>`;
        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch,
        });
        disableHookAnimation(target);
        const afterGroupHook = target.querySelector(".o_form_sheet > .o_web_studio_hook");

        const drag1 = await drag(
            target.querySelector(".o_web_studio_field_type_container .o_web_studio_field_tabs")
        );
        await drag1.moveTo(afterGroupHook);
        assert.containsOnce(
            target,
            ".o_web_studio_nearest_hook",
            "There should be 1 highlighted hook"
        );
        await drag1.cancel();

        const drag2 = await drag(
            target.querySelector(".o_web_studio_field_type_container .o_web_studio_field_columns")
        );
        await drag2.moveTo(afterGroupHook);
        assert.containsOnce(
            target,
            ".o_web_studio_nearest_hook",
            "There should be 1 highlighted hook"
        );
        await drag2.cancel();
    });

    QUnit.test("form: onchange is resilient to errors -- debug mode", async (assert) => {
        const _console = window.console;
        window.console = Object.assign(Object.create(_console), {
            warn(msg) {
                assert.step(msg);
            },
        });
        registerCleanup(() => {
            window.console = _console;
        });
        patchWithCleanup(odoo, {
            debug: true,
        });
        await createViewEditor({
            serverData,
            type: "form",
            resModel: "coucou",
            arch: `
            <form>
                <div class="rendered">
                    <field name="name" />
                </div>
            </form>`,
            mockRPC(route, args) {
                if (args.method === "onchange") {
                    assert.step("onchange");
                    const error = new RPCError();
                    error.exceptionName = "odoo.exceptions.ValidationError";
                    error.code = 200;
                    return Promise.reject(error);
                }
            },
        });

        assert.verifySteps([
            "onchange",
            "The onchange triggered an error. It may indicate either a faulty call to onchange, or a faulty model python side",
        ]);
        assert.containsOnce(target, ".rendered");
    });
});

QUnit.module("View Editors", (hooks) => {
    hooks.beforeEach(() => {
        target = getFixture();
        serverData = getFormEditorServerData();

        serverData.models.coucou.fields.product_ids = { type: "one2many", relation: "product" };
        serverData.models.coucou.records = [{ id: 1, display_name: "Coucou 11", product_ids: [1] }];

        serverData.models.product.fields.m2m = {
            string: "M2M",
            type: "many2many",
            relation: "product",
        };
        serverData.models.product.records = [{ id: 1, display_name: "xpad" }];

        serverData.actions = {};
        serverData.views = {};

        serverData.actions["studio.coucou_action"] = {
            id: 99,
            xml_id: "studio.coucou_action",
            name: "coucouAction",
            res_model: "coucou",
            type: "ir.actions.act_window",
            views: [[false, "list"]],
        };
        serverData.views["coucou,false,list"] = `<tree></tree>`;
        serverData.views["coucou,false,search"] = `<search></search>`;
        registerStudioDependencies();
    });

    QUnit.module("X2many Navigation");

    QUnit.test(
        "edit one2many form view (2 level) and check that the correct model is passed",
        async function (assert) {
            const action = serverData.actions["studio.coucou_action"];
            action.views = [[1, "form"]];
            action.res_model = "coucou";
            action.res_id = 1;
            serverData.views["coucou,1,form"] = /*xml */ `
               <form>
                   <sheet>
                       <field name="display_name"/>
                       <field name="product_ids">
                           <form>
                               <sheet>
                                <group>
                                   <field name="m2m" widget='many2many_tags'/>
                                </group>
                               </sheet>
                           </form>
                       </field>
                   </sheet>
               </form>`;

            Object.assign(serverData.views, {
                "product,2,list": "<tree><field name='display_name'/></tree>",
                "partner,3,list": "<tree><field name='display_name'/></tree>",
            });

            const webClient = await createEnterpriseWebClient({
                serverData,
                mockRPC: (route, args) => {
                    if (route === "/web_studio/edit_view") {
                        assert.step("edit_view");
                        assert.equal(args.model, "product");
                        assert.deepEqual(args.operations, [
                            {
                                type: "attributes",
                                target: {
                                    tag: "field",
                                    attrs: {
                                        name: "m2m",
                                    },
                                    xpath_info: [
                                        {
                                            tag: "form",
                                            indice: 1,
                                        },
                                        {
                                            tag: "sheet",
                                            indice: 1,
                                        },
                                        {
                                            tag: "group",
                                            indice: 1,
                                        },
                                        {
                                            tag: "field",
                                            indice: 1,
                                        },
                                    ],
                                    subview_xpath: "/form[1]/sheet[1]/field[2]/form[1]",
                                },
                                position: "attributes",
                                node: {
                                    tag: "field",
                                    attrs: {
                                        name: "m2m",
                                        widget: "many2many_tags",
                                        can_create: "true",
                                        can_write: "true",
                                    },
                                },
                                new_attrs: {
                                    options: '{"no_create":true}',
                                },
                            },
                        ]);
                    }
                },
            });
            await doAction(webClient, "studio.coucou_action");
            await openStudio(target);

            // edit the x2m form view
            await click(target.querySelector(".o_web_studio_form_view_editor .o_field_one2many"));
            await click(
                target.querySelector(
                    '.o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type="form"]'
                )
            );
            await click(target.querySelector(".o_field_many2many_tags"));
            await click(target.querySelector(".o_web_studio_sidebar_checkbox #no_create"));
            assert.verifySteps(["edit_view"]);
        }
    );

    QUnit.test("display one2many without inline views", async function (assert) {
        serverData.models.product.fields.toughness = {
            manual: true,
            string: "toughness",
            type: "selection",
            selection: [
                ["0", "Hard"],
                ["1", "Harder"],
            ],
        };

        const action = serverData.actions["studio.coucou_action"];
        action.views = [[1, "form"]];
        action.res_model = "coucou";
        serverData.views["coucou,1,form"] = /*xml */ `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids' widget="one2many"/>
                </sheet>
            </form>`;
        serverData.views["coucou,false,search"] = `<search></search>`;
        serverData.views["product,2,list"] = `<tree><field name="toughness"/></tree>`;

        const mockRPC = (route, args) => {
            if (route === "/web_studio/create_inline_view") {
                assert.step("create_inline_view");
                const { model, field_name, subview_type, subview_xpath, view_id } = args;
                assert.strictEqual(model, "product");
                assert.strictEqual(field_name, "product_ids");
                assert.strictEqual(subview_type, "tree");
                assert.strictEqual(subview_xpath, "/form[1]/sheet[1]/field[2]");
                assert.strictEqual(view_id, 1);

                // hardcode inheritance mechanisme
                serverData.views["coucou,1,form"] = /*xml */ `
                    <form>
                        <sheet>
                            <field name='display_name'/>
                            <field name='product_ids'>${serverData.views["product,2,list"]}</field>
                        </sheet>
                    </form>`;
                return serverData.views["product,2,list"];
            }
        };

        const webClient = await createEnterpriseWebClient({ serverData, mockRPC });
        await doAction(webClient, "studio.coucou_action");
        await openStudio(target);
        assert.containsOnce(target, ".o_field_one2many.o_field_widget");

        await click(target.querySelector(".o_web_studio_view_renderer .o_field_one2many"));
        await click(
            target.querySelector(
                '.o_web_studio_view_renderer .o_field_one2many .o_web_studio_editX2Many[data-type="list"]'
            )
        );
        assert.verifySteps(["create_inline_view"]);
    });

    QUnit.test("edit one2many list view", async function (assert) {
        // the 'More' button is only available in debug mode
        patchWithCleanup(odoo, { debug: true });

        const changeArch = makeArchChanger();

        serverData.models["ir.model.fields"] = {
            fields: {
                model: { type: "char" },
            },
            records: [{ id: 54, name: "coucou_id", model: "product" }],
        };
        serverData.views[
            "ir.model.fields,false,form"
        ] = `<form><field name="model" /><field name="id" /></form>`;
        serverData.views["ir.model.fields,false,search"] = `<search />`;

        serverData.models.product.fields.coucou_id = {
            type: "many2one",
            relation: "coucou",
            string: "coucouM2o",
        };

        const action = serverData.actions["studio.coucou_action"];
        action.views = [[1, "form"]];
        action.res_model = "coucou";
        serverData.views["coucou,1,form"] = /*xml */ `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>
                        <tree><field name='display_name'/></tree>
                    </field>
                </sheet>
            </form>`;
        serverData.views["coucou,false,search"] = `<search></search>`;

        const mockRPC = (route, args) => {
            assert.step(route);
            if (route === "/web_studio/get_default_value") {
                assert.step(`get_default_value: ${args.model_name}`);
                return Promise.resolve({});
            }
            if (args.method === "search_read" && args.model === "ir.model.fields") {
                assert.deepEqual(
                    args.kwargs.domain,
                    [
                        ["model", "=", "product"],
                        ["name", "=", "coucou_id"],
                    ],
                    "the model should be correctly set when editing field properties"
                );
            }
            if (route === "/web_studio/edit_view") {
                assert.strictEqual(args.view_id, 1);
                assert.strictEqual(args.operations.length, 1);

                const operation = args.operations[0];
                assert.strictEqual(operation.type, "add");
                assert.strictEqual(operation.position, "before");

                assert.deepEqual(operation.node, {
                    tag: "field",
                    attrs: {
                        name: "coucou_id",
                        optional: "show",
                    },
                });

                const target = operation.target;
                assert.deepEqual(target.attrs, { name: "display_name" });
                assert.strictEqual(target.tag, "field");
                assert.strictEqual(target.subview_xpath, "/form[1]/sheet[1]/field[2]/tree[1]");

                const newArch = /*xml */ `
                    <form>
                        <sheet>
                            <field name='display_name'/>
                            <field name='product_ids'>
                                <tree><field name='coucou_id'/><field name='display_name'/></tree>
                            </field>
                        </sheet>
                    </form>`;

                changeArch(args.view_id, newArch);
            }
        };

        const webClient = await createEnterpriseWebClient({ serverData, mockRPC });
        await doAction(webClient, "studio.coucou_action");
        assert.verifySteps([
            "/web/webclient/load_menus",
            "/web/action/load",
            "/web/dataset/call_kw/coucou/get_views",
            "/web/dataset/call_kw/coucou/onchange",
        ]);
        await openStudio(target);
        assert.verifySteps([
            "/web/dataset/call_kw/coucou/get_views",
            "/web_studio/chatter_allowed",
            "/web_studio/get_studio_view_arch",
            "/web/dataset/call_kw/coucou/onchange",
        ]);

        await click(target.querySelector(".o_web_studio_view_renderer .o_field_one2many"));
        const blockOverlayZindex = target.querySelector(
            ".o_web_studio_view_renderer .o_field_one2many .o-web-studio-edit-x2manys-buttons"
        ).style["z-index"];
        assert.strictEqual(blockOverlayZindex, "1000", "z-index of blockOverlay should be 1000");
        assert.verifySteps(["/web_studio/get_default_value", "get_default_value: coucou"]);

        await click(
            target.querySelector(
                ".o_web_studio_view_renderer .o_field_one2many .o_web_studio_editX2Many"
            )
        );
        assert.verifySteps(["/web/dataset/call_kw/product/fields_get"]);
        assert.containsOnce(
            target,
            ".o_web_studio_view_renderer thead tr [data-studio-xpath]",
            "there should be 1 nodes in the x2m editor."
        );

        await click(target.querySelector(".o_web_studio_existing_fields_header"));
        await dragAndDrop(
            ".o_web_studio_existing_fields_section .o_web_studio_field_many2one",
            ".o_web_studio_hook"
        );
        await nextTick();
        assert.verifySteps(["/web_studio/edit_view"]);

        assert.containsN(
            target,
            ".o_web_studio_view_renderer thead tr [data-studio-xpath]",
            2,
            "there should be 2 nodes after the drag and drop."
        );

        // click on a field in the x2m list view
        await click(target.querySelector(".o_web_studio_view_renderer [data-studio-xpath]"));

        // edit field properties
        assert.containsOnce(
            target,
            ".o_web_studio_sidebar .o_web_studio_parameters",
            "there should be button to edit the field properties"
        );
        await click(target.querySelector(".o_web_studio_sidebar .o_web_studio_parameters"));
        assert.verifySteps([
            "/web/dataset/call_kw/ir.model.fields/search_read",
            "/web/dataset/call_kw/ir.model.fields/get_views",
            "/web/dataset/call_kw/ir.model.fields/read",
        ]);
    });

    QUnit.test(
        "edit one2many list view with widget fieldDependencies and some records",
        async function (assert) {
            serverData.models.product.fields.is_dep = {
                type: "char",
                string: "Dependency from fields_get",
            };
            serverData.models.coucou.records[0] = {
                id: 1,
                display_name: "coucou1",
                product_ids: [1],
            };
            serverData.models.product.records[0] = {
                id: 1,
                is_dep: "the meters",
                display_name: "people say",
            };

            const charField = registry.category("fields").get("char");
            class CharWithDependencies extends charField.component {
                setup() {
                    super.setup();
                    const record = this.props.record;
                    owl.onMounted(() => {
                        assert.step(
                            `widget Dependency: ${JSON.stringify(record.fields.is_dep)} : ${
                                record.data.is_dep
                            }`
                        );
                    });
                }
            }
            registry.category("fields").add("list.withDependencies", {
                ...charField,
                component: CharWithDependencies,
                fieldDependencies: [{ name: "is_dep", type: "char" }],
            });

            const action = serverData.actions["studio.coucou_action"];
            action.res_id = 1;
            action.views = [[1, "form"]];
            action.res_model = "coucou";
            serverData.views["coucou,1,form"] = /*xml */ `<form>
            <sheet>
                <field name='display_name'/>
                <field name='product_ids'>
                    <tree><field name='display_name' widget="withDependencies"/></tree>
                </field>
            </sheet>
        </form>`;
            const mockRPC = (route, args) => {
                if (args.method === "fields_get") {
                    assert.step("fields_get");
                }
            };
            const webClient = await createEnterpriseWebClient({ serverData, mockRPC });
            await doAction(webClient, "studio.coucou_action");
            assert.verifySteps([`widget Dependency: {"name":"is_dep","type":"char"} : the meters`]);
            await openStudio(target);
            assert.verifySteps([`widget Dependency: {"name":"is_dep","type":"char"} : the meters`]);

            assert.containsOnce(target, ".o_web_studio_form_view_editor");
            await click(target.querySelector(".o_field_one2many"));
            await click(target.querySelector(".o_field_one2many .o_web_studio_editX2Many"));

            assert.verifySteps([
                "fields_get",
                `widget Dependency: {"type":"char","string":"Dependency from fields_get","name":"is_dep"} : the meters`,
            ]);
            assert.containsOnce(target, ".o_web_studio_list_view_editor");
        }
    );

    QUnit.test("entering x2many with view widget", async (assert) => {
        class MyWidget extends owl.Component {}
        MyWidget.template = owl.xml`<div class="myWidget" />`;
        const myWidget = {
            component: MyWidget,
        };
        registry.category("view_widgets").add("myWidget", myWidget);

        serverData.models.coucou.records[0] = {
            id: 1,
            display_name: "coucou1",
            product_ids: [1],
        };
        serverData.models.product.records[0] = {
            id: 1,
            display_name: "people say",
        };

        const action = serverData.actions["studio.coucou_action"];
        action.res_id = 1;
        action.views = [[1, "form"]];
        action.res_model = "coucou";
        serverData.views["coucou,1,form"] = /*xml */ `<form>
            <sheet>
                <field name='display_name'/>
                <field name='product_ids'>
                    <tree><widget name="myWidget"/></tree>
                </field>
            </sheet>
        </form>`;
        const webClient = await createEnterpriseWebClient({ serverData });
        await doAction(webClient, "studio.coucou_action");
        await openStudio(target);

        assert.containsOnce(target, ".o_web_studio_form_view_editor");
        assert.containsOnce(target, ".myWidget");

        await click(target, ".o_web_studio_view_renderer .o_field_one2many");
        await click(
            target,
            ".o_web_studio_view_renderer .o_field_one2many .o_web_studio_editX2Many[data-type='list']"
        );
        assert.containsOnce(target, ".o_web_studio_list_view_editor");
        assert.containsOnce(target, ".myWidget");
    });

    QUnit.test("edit one2many list view with tree_view_ref context key", async function (assert) {
        const action = serverData.actions["studio.coucou_action"];
        action.views = [[1, "form"]];
        action.res_model = "coucou";
        serverData.views["coucou,1,form"] = /*xml */ `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids' widget="one2many" context="{'tree_view_ref': 'module.tree_view_ref'}" />
                </sheet>
            </form>`;

        serverData.views["coucou,false,search"] = `<search></search>`;
        serverData.views[
            "product,module.tree_view_ref,list"
        ] = /*xml */ `<tree><field name="display_name"/></tree>`;

        const mockRPC = (route, args) => {
            if (route === "/web_studio/create_inline_view") {
                assert.step("create_inline_view");
                assert.equal(
                    args.context.tree_view_ref,
                    "module.tree_view_ref",
                    "context tree_view_ref should be propagated for inline view creation"
                );

                const { model, field_name, subview_type, subview_xpath, view_id } = args;
                assert.strictEqual(model, "product");
                assert.strictEqual(field_name, "product_ids");
                assert.strictEqual(subview_type, "tree");
                assert.strictEqual(subview_xpath, "/form[1]/sheet[1]/field[2]");
                assert.strictEqual(view_id, 1);

                // hardcode inheritance mechanisme
                serverData.views["coucou,1,form"] = /*xml */ `
                    <form>
                        <sheet>
                            <field name='display_name'/>
                            <field name='product_ids'>${serverData.views["product,module.tree_view_ref,list"]}</field>
                        </sheet>
                    </form>`;
                return serverData.views["product,module.tree_view_ref,list"];
            }
        };

        const webClient = await createEnterpriseWebClient({ serverData, mockRPC });
        await doAction(webClient, "studio.coucou_action");
        await openStudio(target);

        await click(target.querySelector(".o_web_studio_view_renderer .o_field_one2many"));
        await click(
            target.querySelector(
                ".o_web_studio_view_renderer .o_field_one2many .o_web_studio_editX2Many"
            )
        );
        assert.verifySteps(["create_inline_view"]);
    });

    QUnit.test(
        "edit one2many form view (2 level) and check chatter allowed",
        async function (assert) {
            const pyEnv = await startServer();

            const partnerId = pyEnv["partner"].create({
                name: "jean",
            });

            const productId = pyEnv["product"].create({
                display_name: "xpad",
                partner_ids: [[5], [4, partnerId, false]],
            });

            const coucouId1 = pyEnv["coucou"].create({
                display_name: "Coucou 11",
                product_ids: [[5], [4, productId, false]],
            });

            const action = serverData.actions["studio.coucou_action"];
            action.views = [[1, "form"]];
            action.res_model = "coucou";
            action.res_id = coucouId1;
            serverData.views["coucou,1,form"] = /*xml */ `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>
                        <form>
                            <sheet>
                                <group>
                                    <field name='partner_ids'>
                                        <form><sheet><group><field name='display_name'/></group></sheet></form>
                                    </field>
                                </group>
                            </sheet>
                        </form>
                    </field>
                </sheet>
            </form>`;

            Object.assign(serverData.views, {
                "product,2,list": "<tree><field name='display_name'/></tree>",
                "partner,3,list": "<tree><field name='display_name'/></tree>",
            });

            serverData.views["coucou,false,search"] = `<search></search>`;

            const mockRPC = (route, args) => {
                assert.step(route);
                if (route === "/web_studio/chatter_allowed") {
                    return true;
                }
                if (args.method === "name_search" && args.model === "ir.model.fields") {
                    assert.deepEqual(
                        args.kwargs.args,
                        [
                            ["relation", "=", "partner"],
                            ["ttype", "in", ["many2one", "many2many"]],
                            ["store", "=", true],
                        ],
                        "the domain should be correctly set when searching for a related field for new button"
                    );
                }
            };

            const { webClient } = await start({
                serverData,
                mockRPC,
            });

            assert.verifySteps([
                "/web/webclient/load_menus",
                "/mail/init_messaging",
                "/web/dataset/call_kw/res.users/systray_get_activities",
                "/mail/load_message_failures",
            ]);

            await doAction(webClient, "studio.coucou_action");
            assert.verifySteps([
                "/web/action/load",
                "/web/dataset/call_kw/coucou/get_views",
                "/web/dataset/call_kw/coucou/read",
            ]);
            await openStudio(target);
            assert.verifySteps([
                "/web/dataset/call_kw/coucou/get_views",
                "/web_studio/chatter_allowed",
                "/web_studio/get_studio_view_arch",
                "/web/dataset/call_kw/coucou/read",
            ]);

            assert.containsOnce(
                target,
                ".o_web_studio_add_chatter",
                "should be possible to add a chatter"
            );

            await click(target.querySelector(".o_web_studio_view_renderer .o_field_one2many"));
            assert.verifySteps(["/web_studio/get_default_value"]);

            await click(
                target.querySelector(
                    '.o_web_studio_view_renderer .o_field_one2many .o_web_studio_editX2Many[data-type="form"]'
                )
            );
            assert.containsNone(
                target,
                ".o_web_studio_add_chatter",
                "should not be possible to add a chatter"
            );
            assert.verifySteps([
                "/web/dataset/call_kw/product/fields_get",
                "/web/dataset/call_kw/partner/get_views",
                "/web/dataset/call_kw/product/read",
            ]);

            await click(target.querySelector(".o_web_studio_view_renderer .o_field_one2many"));
            assert.verifySteps(["/web_studio/get_default_value"]);
            await click(
                target.querySelector(
                    '.o_web_studio_view_renderer .o_field_one2many .o_web_studio_editX2Many[data-type="form"]'
                )
            );
            assert.verifySteps([
                "/web/dataset/call_kw/partner/fields_get",
                "/web/dataset/call_kw/partner/read",
            ]);

            assert.strictEqual(
                target.querySelector(".o_field_char").textContent,
                "jean",
                "the partner view form should be displayed."
            );

            disableHookAnimation(target);
            await dragAndDrop(
                target.querySelector(".o_web_studio_new_fields .o_web_studio_field_char"),
                target.querySelector(".o_inner_group .o_web_studio_hook")
            );
            assert.verifySteps(["/web_studio/edit_view"]);

            // add a new button
            await click(
                target.querySelector(".o_web_studio_form_view_editor .o_web_studio_button_hook")
            );
            assert.verifySteps([]);

            assert.containsOnce(target, ".modal .o_web_studio_new_button_dialog");
            await click(
                target.querySelector(
                    ".modal .o_web_studio_new_button_dialog .o_input_dropdown input"
                )
            );
            assert.verifySteps(["/web/dataset/call_kw/ir.model.fields/name_search"]);
        }
    );

    QUnit.test(
        "edit one2many list view that uses parent key [REQUIRE FOCUS]",
        async function (assert) {
            const pyEnv = await startServer();

            const partnerId = pyEnv["partner"].create({
                name: "jacques",
            });

            const productId = pyEnv["product"].create({
                display_name: "xpad",
                m2o: partnerId,
            });

            const coucouId1 = pyEnv["coucou"].create({
                display_name: "Coucou 11",
                product_ids: [[5], [4, productId, false]],
            });

            const action = serverData.actions["studio.coucou_action"];
            action.views = [[1, "form"]];
            action.res_model = "coucou";
            action.res_id = coucouId1;
            serverData.views["coucou,1,form"] = /*xml */ `
           <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>
                        <form>
                            <sheet>
                                <field name="m2o"
                                       attrs="{'invisible': [('parent.display_name', '=', 'coucou')]}"
                                       domain="[('display_name', '=', parent.display_name)]" />
                            </sheet>
                        </form>
                    </field>
                </sheet>
            </form>`;

            Object.assign(serverData.views, {
                "product,2,list": "<tree><field name='display_name'/></tree>",
            });

            serverData.views["coucou,false,search"] = `<search></search>`;

            registry.category("services").add("field", fieldService);

            const webClient = await createEnterpriseWebClient({ serverData });
            await doAction(webClient, "studio.coucou_action");
            await openStudio(target);

            // edit the x2m form view
            await click(target.querySelector(".o_web_studio_form_view_editor .o_field_one2many"));
            await click(
                target.querySelector(
                    '.o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type="form"]'
                )
            );
            assert.strictEqual(
                target.querySelector('.o_web_studio_form_view_editor .o_field_widget[name="m2o"]')
                    .textContent,
                "jacques",
                "the x2m form view should be correctly rendered"
            );
            await click(
                target.querySelector('.o_web_studio_form_view_editor .o_field_widget[name="m2o"]')
            );

            // open the domain editor
            assert.containsNone(target, ".modal");
            assert.strictEqual(
                target.querySelector(".o_web_studio_sidebar input#domain").value,
                "[('display_name', '=', parent.display_name)]"
            );

            await click(target.querySelector(".o_web_studio_sidebar input#domain"));
            assert.containsOnce(target, ".modal");
            assert.strictEqual(
                target.querySelector(".modal .modal-body").textContent,
                "This domain is not supported."
            );
        }
    );

    QUnit.test("move a field in one2many list", async function (assert) {
        const pyEnv = await startServer();

        const coucouId1 = pyEnv["coucou"].create({
            display_name: "Coucou 11",
            product_ids: pyEnv["product"].search([["display_name", "=", "xpad"]]),
        });

        const action = serverData.actions["studio.coucou_action"];
        action.views = [[1, "form"]];
        action.res_model = "coucou";
        action.res_id = coucouId1;
        serverData.views["coucou,1,form"] = /*xml */ `
            <form>
                <sheet>
                    <field name='display_name'/>
                    <field name='product_ids'>
                        <tree>
                            <field name='m2o'/>
                            <field name='coucou_id'/>
                        </tree>
                    </field>
                </sheet>
            </form>`;

        serverData.views["coucou,false,search"] = `<search></search>`;

        const mockRPC = (route, args) => {
            if (route === "/web_studio/edit_view") {
                assert.step("edit_view");
                assert.deepEqual(
                    args.operations[0],
                    {
                        node: {
                            tag: "field",
                            attrs: { name: "coucou_id" },
                            subview_xpath: "/form[1]/sheet[1]/field[2]/tree[1]",
                        },
                        position: "before",
                        target: {
                            tag: "field",
                            attrs: { name: "m2o" },
                            subview_xpath: "/form[1]/sheet[1]/field[2]/tree[1]",
                            xpath_info: [
                                {
                                    indice: 1,
                                    tag: "tree",
                                },
                                {
                                    indice: 1,
                                    tag: "field",
                                },
                            ],
                        },
                        type: "move",
                    },
                    "the move operation should be correct"
                );
            }
        };

        const webClient = await createEnterpriseWebClient({ serverData, mockRPC });
        await doAction(webClient, "studio.coucou_action");
        await openStudio(target);

        // edit the x2m form view
        await click(target.querySelector(".o_web_studio_form_view_editor .o_field_one2many"));
        await click(
            target.querySelector(
                '.o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type="list"]'
            )
        );

        assert.strictEqual(
            Array.from(target.querySelectorAll(".o_web_studio_list_view_editor th"))
                .map((el) => el.textContent)
                .join(""),
            "M2Ocoucou",
            "the columns should be in the correct order"
        );

        // move coucou at index 0
        await dragAndDrop(
            selectorContains(target, ".o_web_studio_list_view_editor th", "coucou"),
            target.querySelector("th.o_web_studio_hook")
        );
        assert.verifySteps(["edit_view"]);
    });

    QUnit.test("One2Many list editor column_invisible in attrs ", async function (assert) {
        const pyEnv = await startServer();
        pyEnv["coucou"].create({
            display_name: "Coucou 11",
            product_ids: pyEnv["product"].search([["display_name", "=", "xpad"]]),
        });

        const action = serverData.actions["studio.coucou_action"];
        action.views = [[1, "form"]];
        action.res_model = "coucou";
        serverData.views["coucou,1,form"] = /*xml */ `
        <form>
            <field name='product_ids'>
                <tree>
                    <field name="display_name" attrs="{'column_invisible': [('parent.id', '=',False)]}" />
                </tree>
            </field>
        </form>`;

        serverData.views["coucou,false,search"] = `<search></search>`;

        const mockRPC = (route, args) => {
            if (route === "/web_studio/edit_view") {
                assert.step("edit_view");
                assert.deepEqual(
                    args.operations[0].new_attrs.attrs,
                    { column_invisible: [["parent.id", "=", false]] },
                    'we should send "column_invisible" in attrs.attrs'
                );

                assert.equal(
                    args.operations[0].new_attrs.readonly,
                    "1",
                    'We should send "readonly" in the node attr'
                );
            }
        };

        const webClient = await createEnterpriseWebClient({ serverData, mockRPC });
        await doAction(webClient, "studio.coucou_action");
        await openStudio(target);

        // Enter edit mode of the O2M
        await click(target.querySelector(".o_field_one2many[name=product_ids]"));
        await click(target.querySelector('.o_web_studio_editX2Many[data-type="list"]'));

        await click(selectorContains(target, ".o_web_studio_sidebar .nav-link", "View"));
        await click(target.querySelector(".o_web_studio_sidebar input#show_invisible"));

        // select the first column
        await click(target.querySelector("thead th[data-studio-xpath]"));
        // enable readonly
        await click(target.querySelector(".o_web_studio_sidebar input#readonly"));
        assert.verifySteps(["edit_view"]);
    });

    QUnit.test(
        "One2Many form datapoint doesn't contain the parent datapoint",
        async function (assert) {
            /*
             * OPW-2125214
             * When editing a child o2m form with studio, the fields_get method tries to load
             * the parent fields too. This is not allowed anymore by the ORM.
             * It happened because, before, the child datapoint contained the parent datapoint's data
             */
            assert.expect(1);
            const pyEnv = await startServer();
            const coucouId1 = pyEnv["coucou"].create({
                display_name: "Coucou 11",
                product_ids: [],
            });

            const action = serverData.actions["studio.coucou_action"];
            action.views = [[1, "form"]];
            action.res_model = "coucou";
            action.res_id = coucouId1;
            serverData.views["coucou,1,form"] = /*xml */ `
           <form>
               <field name='product_ids'>
                    <form>
                        <field name="display_name" />
                        <field name="toughness" />
                    </form>
               </field>
           </form>`;

            serverData.views["coucou,false,search"] = `<search></search>`;
            serverData.views["product,2,list"] = `<tree><field name="display_name" /></tree>`;

            const mockRPC = async (route, args) => {
                if (args.method === "onchange" && args.model === "product") {
                    const fields = args.args[3];
                    assert.deepEqual(Object.keys(fields), ["display_name", "toughness"]);
                }
            };

            const webClient = await createEnterpriseWebClient({ serverData, mockRPC });
            await doAction(webClient, "studio.coucou_action");
            await openStudio(target);

            await click(target.querySelector(".o_web_studio_form_view_editor .o_field_one2many"));
            await click(
                target.querySelector(
                    '.o_web_studio_form_view_editor .o_field_one2many .o_web_studio_editX2Many[data-type="form"]'
                )
            );
        }
    );
});