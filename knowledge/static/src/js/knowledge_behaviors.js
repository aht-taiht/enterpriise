/** @odoo-module */

import Class from 'web.Class';

/**
 * Behavior to be injected through @see FieldHtmlInjector to @see OdooEditor
 * blocks which have specific classes calling for such behaviors.
 *
 * A typical usage could be the following:
 * - An @see OdooEditor block like /template has the generic class:
 *   @see o_knowledge_behavior_anchor to signify that it needs to have a
 *   behavior injected.
 * - This block also has the specific class:
 *   @see o_knowledge_behavior_type_[behaviorType] which specifies the type of
 *   behavior that needs to be injected. @see FieldHtmlInjector has a dictionary
 *   mapping those classes to the correct behavior class.
 *
 * The @see KnowledgeBehavior is a basic behavior intended to be overriden for
 * more complex implementations
 */
const KnowledgeBehavior = Class.extend({
    /**
     * @param {Widget} handler @see FieldHtmlInjector which has access to
     *                         widget specific functions
     * @param {Element} anchor dom node to apply the behavior to
     * @param {string} mode edit/readonly
     * @param {Integer} articleId this id of the currently edited knowledge.article
     */
    init: function (handler, anchor, mode, articleId) {
        this.handler = handler;
        this.anchor = anchor;
        this.mode = mode;
        this.articleId = articleId;
        if (this.handler.editor) {
            this.handler.editor.observerUnactive('knowledge_attributes');
        }
        this.applyAttributes();
        if (this.handler.editor) {
            this.handler.editor.observerActive('knowledge_attributes');
        }
        this.applyListeners();
    },
    /**
     * Add specific attributes related to this behavior to this.anchor
     */
    applyAttributes: function () {},
    /**
     * Add specific listeners related to this behavior to this.anchor
     */
    applyListeners: function () {},
    /**
     * Disable the listeners added in @see applyListeners
     */
    disableListeners: function () {},
    /**
     * Used by @see KnowledgePlugin to remove behaviors when the field_html is
     * saved. Also used by @see FieldHtmlInjector to manage injected behaviors
     */
    removeBehavior: function () {
        this.handler.trigger_up('behavior_removed', {
            anchor: this.anchor,
        });
        this.disableListeners();
        delete this.anchor.oKnowledgeBehavior;
    },
});

export {
    KnowledgeBehavior
};
