/** @odoo-module **/

import { patchUiSize, SIZES } from "@mail/../tests/helpers/patch_ui_size";
import {
    click,
    contains,
    dragenterFiles,
    dropFiles,
    start,
    startServer,
} from "@mail/../tests/helpers/test_utils";

import { file } from "@web/../tests/legacy/helpers/test_utils";
const { createFile, inputFiles } = file;

QUnit.module("attachment preview");

QUnit.test("Should not have attachment preview for still uploading attachment", async (assert) => {
    const pyEnv = await startServer();
    const recordId = pyEnv["mail.test.simple.main.attachment"].create({});
    const views = {
        "mail.test.simple.main.attachment,false,form": `
            <form string="Test document">
                <sheet>
                    <field name="name"/>
                </sheet>
                <div class="o_attachment_preview"/>
                <div class="oe_chatter">
                    <field name="message_ids"/>
                </div>
            </form>`,
    };
    patchUiSize({ size: SIZES.XXL });
    const { openFormView } = await start({
        async mockRPC(route, args) {
            if (String(route).includes("/web/static/lib/pdfjs/web/viewer.html")) {
                assert.step("pdf viewer");
            }
            if (route === "/mail/attachment/upload") {
                await new Promise(() => {});
            }
        },
        serverData: { views },
    });
    openFormView("mail.test.simple.main.attachment", recordId);
    dragenterFiles((await contains(".o-mail-Chatter"))[0]);
    const files = [await createFile({ name: "invoice.pdf", contentType: "application/pdf" })];
    dropFiles((await contains(".o-mail-Dropzone"))[0], files);
    await contains(".o-mail-Dropzone", 0);
    await contains(".o-mail-Attachment", 0);
    assert.verifySteps(
        [],
        "The page should never render a PDF while it is uploading, as the uploading is blocked in this test we should never render a PDF preview"
    );
});

QUnit.test("Attachment on side", async (assert) => {
    const pyEnv = await startServer();
    const recordId = pyEnv["mail.test.simple.main.attachment"].create({});
    const attachmentId = pyEnv["ir.attachment"].create({
        mimetype: "image/jpeg",
        res_id: recordId,
        res_model: "mail.test.simple.main.attachment",
    });
    pyEnv["mail.message"].create({
        attachment_ids: [attachmentId],
        model: "mail.test.simple.main.attachment",
        res_id: recordId,
    });
    const views = {
        "mail.test.simple.main.attachment,false,form": `
            <form string="Test document">
                <sheet>
                    <field name="name"/>
                </sheet>
                <div class="o_attachment_preview"/>
                <div class="oe_chatter">
                    <field name="message_ids"/>
                </div>
            </form>`,
    };
    patchUiSize({ size: SIZES.XXL });
    const { openFormView } = await start({
        mockRPC(route, args) {
            if (String(route).includes("/web/static/lib/pdfjs/web/viewer.html")) {
                var canvas = document.createElement("canvas");
                return canvas.toDataURL();
            }
        },
        serverData: { views },
    });
    openFormView("mail.test.simple.main.attachment", recordId);
    await contains(".o-mail-Attachment-imgContainer > img");
    await contains(".o_form_sheet_bg > .o-mail-Form-chatter");
    assert.doesNotHaveClass($(".o-mail-Form-chatter"), "o-aside");
    await contains(".o_form_sheet_bg + .o_attachment_preview");

    // Don't display arrow if there is no previous/next element
    await contains(".arrow", 0);

    // send a message with attached PDF file
    await click("button", { text: "Send message" });
    const files = [await createFile({ name: "invoice.pdf", contentType: "application/pdf" })];
    inputFiles((await contains(".o-mail-Composer-coreMain .o_input_file"))[0], files);
    await click(".o-mail-Composer-send:not(:disabled)");
    await contains(".arrow", 2);

    await click(".o_move_next");
    await contains(".o-mail-Attachment-imgContainer > img", 0);
    await contains(".o-mail-Attachment > iframe");

    await click(".o_move_previous");
    await contains(".o-mail-Attachment-imgContainer > img");
});

QUnit.test(
    "After switching record with the form pager, when using the attachment preview navigation, the attachment should be switched",
    async () => {
        const pyEnv = await startServer();
        const recordId_1 = pyEnv["mail.test.simple.main.attachment"].create({
            display_name: "first partner",
            message_attachment_count: 2,
        });
        const attachmentId_1 = pyEnv["ir.attachment"].create({
            mimetype: "image/jpeg",
            res_id: recordId_1,
            res_model: "mail.test.simple.main.attachment",
        });
        pyEnv["mail.message"].create({
            attachment_ids: [attachmentId_1],
            model: "mail.test.simple.main.attachment",
            res_id: recordId_1,
        });
        const attachmentId_2 = pyEnv["ir.attachment"].create({
            mimetype: "application/pdf",
            res_id: recordId_1,
            res_model: "mail.test.simple.main.attachment",
        });
        pyEnv["mail.message"].create({
            attachment_ids: [attachmentId_2],
            model: "mail.test.simple.main.attachment",
            res_id: recordId_1,
        });

        const recordId_2 = pyEnv["mail.test.simple.main.attachment"].create({
            display_name: "second partner",
            message_attachment_count: 0,
        });
        const views = {
            "mail.test.simple.main.attachment,false,form": `
                <form string="Test document">
                    <sheet>
                        <field name="name"/>
                    </sheet>
                    <div class="o_attachment_preview"/>
                    <div class="oe_chatter">
                        <field name="message_ids"/>
                    </div>
                </form>`,
        };
        patchUiSize({ size: SIZES.XXL });
        const { openFormView } = await start({
            serverData: { views },
            async mockRPC(route, args) {
                if (route.includes("/web/static/lib/pdfjs/web/viewer.html")) {
                    return document.createElement("canvas").toDataURL();
                }
            },
        });
        openFormView("mail.test.simple.main.attachment", recordId_1, {
            props: { resIds: [recordId_1, recordId_2] },
        });
        await contains(".o_pager_counter", 1, { text: "1 / 2" });
        await click(".o_pager_next");
        await contains(".o_pager_counter", 1, { text: "2 / 2" });
        await click(".o_pager_previous");
        await contains(".o_pager_counter", 1, { text: "1 / 2" });
        await contains(".arrow", 2);
        await click(".o-mail-Attachment .o_move_next");
        await contains(".o-mail-Attachment-imgContainer img");
        await click(".o-mail-Attachment .o_move_previous");
        await contains(".o-mail-Attachment iframe");
    }
);

QUnit.test("Attachment on side on new record", async () => {
    const views = {
        "mail.test.simple.main.attachment,false,form": `
            <form string="Test document">
                <sheet>
                    <field name="name"/>
                </sheet>
                <div class="o_attachment_preview"/>
                <div class="oe_chatter">
                    <field name="message_ids"/>
                </div>
            </form>`,
    };
    patchUiSize({ size: SIZES.XXL });
    const { openFormView } = await start({ serverData: { views } });
    openFormView("mail.test.simple.main.attachment", undefined, {
        waitUntilDataLoaded: false,
        waitUntilMessagesLoaded: false,
    });
    await contains(".o_form_sheet_bg + .o-mail-Form-chatter");
    await contains(".o_attachment_preview", 0);
});

QUnit.test("Attachment on side not displayed on smaller screens", async () => {
    const pyEnv = await startServer();
    const recordId = pyEnv["mail.test.simple.main.attachment"].create({});
    const attachmentId = pyEnv["ir.attachment"].create({
        mimetype: "image/jpeg",
        res_id: recordId,
        res_model: "mail.test.simple.main.attachment",
    });
    pyEnv["mail.message"].create({
        attachment_ids: [attachmentId],
        model: "mail.test.simple.main.attachment",
        res_id: recordId,
    });
    const views = {
        "mail.test.simple.main.attachment,false,form": `
            <form string="Test document">
                <sheet>
                    <field name="name"/>
                </sheet>
                <div class="o_attachment_preview"/>
                <div class="oe_chatter">
                    <field name="message_ids"/>
                </div>
            </form>`,
    };
    patchUiSize({ size: SIZES.XL });
    const { openFormView } = await start({ serverData: { views } });
    openFormView("mail.test.simple.main.attachment", recordId);
    await contains(".o_form_sheet_bg + .o-mail-Form-chatter");
    await contains(".o_attachment_preview", 0);
});
