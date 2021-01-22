odoo.define('mail_enterprise/static/src/components/chatter_container/chatter_container.js', function (require) {
'use strict';

const ChatterContainer = require('mail/static/src/components/chatter_container/chatter_container.js');

Object.assign(ChatterContainer, {
    defaultProps: Object.assign(ChatterContainer.defaultProps || {}, {
        isInFormSheetBg: false,
    }),
    props: Object.assign(ChatterContainer.props, {
        isInFormSheetBg: {
            type: Boolean,
        },
    })
});

});
