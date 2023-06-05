/* @odoo-module */

import { EmojiPicker } from "@mail/core/common/emoji_picker";

import { patch } from "@web/core/utils/patch";

EmojiPicker.props.push("hasRemoveFeature?");

patch(EmojiPicker.prototype, "knowledge", {
    removeEmoji() {
        this.props.onSelect(false);
        this.gridRef.el.scrollTop = 0;
        this.props.close?.();
        this.props.onClose?.();
    },
});
