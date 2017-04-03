odoo.define('web_studio.GraphEditor', function (require) {
"use strict";

var GraphRenderer = require('web.GraphRenderer');

return GraphRenderer.extend({
    /**
     * @override
     */
    start: function () {
        // The graph renderer is currently wrapped inside a div ; this is
        // defined in the graph controller. To keep the same style, we keep
        // the same dom here.

        // TODO: this is clearly a hack ; the renderer should be the only
        // widget defining its own dom (not its controller).
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            // the actual rendering is done in a setTimeout and we need to do
            // this after it
            _.defer(function() {
                self.$el.wrap($('<div>', {
                    class: 'o_graph',
                }));
                self.setElement(self.$el.parent());
            });
        });
    },
});

});
