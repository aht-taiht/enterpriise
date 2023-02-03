/** @odoo-module **/

import { registry } from '@web/core/registry';
import { TabletImageField, tabletImageField } from "@quality/tablet_image_field/tablet_image_field";
import { useIotDevice } from '@iot/iot_device_hook';
import { useService } from '@web/core/utils/hooks';
import { WarningDialog } from '@web/core/errors/error_dialogs';
import { IoTConnectionErrorDialog } from '@iot/iot_connection_error_dialog';

export class TabletImageIoTField extends TabletImageField {
    setup() {
        super.setup();
        this.dialog = useService('dialog');
        this.notification = useService('notification');
        this.getIotDevice = useIotDevice({
            getIotIp: () => {
                if (this.props.record.data.test_type === 'picture') {
                    return this.props.record.data[this.props.ip_field];
                }
            },
            getIdentifier: () => {
                if (this.props.record.data.test_type === 'picture') {
                    return this.props.record.data[this.props.identifier_field];
                }
            },
            onValueChange: (data) => {
                if (data.owner && data.owner === data.session_id) {
                    this.notification.add(data.message);
                    if (data.image) {
                        this.props.update(data.image);
                    }
                }
            },
        });
    }
    async onTakePicture(ev) {
        if (this.getIotDevice()) {
            // Stop propagating so that the FileUploader component won't open the file dialog.
            ev.stopImmediatePropagation();
            ev.preventDefault();
            this.notification.add(this.env._t('Capture image...'));
            try {
                const data = await this.getIotDevice().action({});
                if (data.result !== true) {
                    this.dialog.add(WarningDialog, {
                        title: this.env._t('Connection to device failed'),
                        message: this.env._t('Please check if the device is still connected.'),
                    });
                }
                return data;
            } catch {
                this.dialog.add(IoTConnectionErrorDialog, { href: this.props.record.data[this.props.ip_field] });
            }
        }
    }
}
TabletImageIoTField.props = {
    ...TabletImageField.props,
    ip_field: { type: String },
    identifier_field: { type: String },
};
TabletImageIoTField.template = 'quality_iot.TabletImageIoTField';

export const tabletImageIoTField = {
    ...tabletImageField,
    component: TabletImageIoTField,
    extractProps: (params) => ({
        ...tabletImageField.extractProps(params),
        ip_field: params.attrs.options.ip_field,
        identifier_field: params.attrs.options.identifier,
    }),
};

registry.category("fields").add("iot_picture", tabletImageIoTField);
