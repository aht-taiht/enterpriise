/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { findInvalidEmailFromText } from  "./utils.js"
import { _t } from "@web/core/l10n/translation";

publicWidget.registry.appointmentForm = publicWidget.Widget.extend({
    selector: '.o_appointment_attendee_form',
    events: {
        'click div.o_appointment_add_guests button.btn-link': '_onAddGuest',
        'click div.o_appointment_add_guests button.btn-close': '_onHideGuest',
        'click .o_appointment_form_confirm_btn': '_onConfirmAppointment',
    },

    /**
     * This function will show the guest email textarea where user can enter the
     * emails of the guests if allow_guests option is enabled.
     */
    _onAddGuest: function(){
        const textArea = this.el.querySelector('#o_appointment_input_guest_emails');
        textArea.classList.remove('d-none');
        textArea.focus();
        const addGuestDiv = this.el.querySelector('div.o_appointment_add_guests')
        addGuestDiv.querySelector('button.btn-link').classList.add('d-none')
        addGuestDiv.querySelector('label.fw-bold').classList.remove('d-none')
        addGuestDiv.querySelector('button.btn-close').classList.remove('d-none')
    },

    _onConfirmAppointment: async function(event) {
        this._validateCheckboxes();
        const textArea = this.el.querySelector('#o_appointment_input_guest_emails');
        const appointmentForm = document.querySelector('.appointment_submit_form');
        if (!textArea || textArea.value.trim() === '') {
            appointmentForm.submit();
        } else {
            let emailInfo = findInvalidEmailFromText(textArea.value)
            if (emailInfo.invalidEmails.length || emailInfo.emailList.length > 10) {
                const errorMessage = emailInfo.invalidEmails.length > 0 ? _t('Invalid Email') : _t("You cannot invite more than 10 people");
                this._showErrorMsg(errorMessage);
            } else {
                this._hideErrorMsg();
                appointmentForm.submit();
            }
        }
    },

    /**
     * This function will hide the guest email textarea if allow_guests option is enabled.
     */
    _onHideGuest: function() {
        this._hideErrorMsg();
        const textArea = this.el.querySelector('#o_appointment_input_guest_emails');
        textArea.classList.add('d-none')
        textArea.value = "";
        const addGuestDiv = this.el.querySelector('div.o_appointment_add_guests')
        addGuestDiv.querySelector('button.btn-link').classList.remove('d-none');
        addGuestDiv.querySelector('label.fw-bold').classList.add('d-none');
        addGuestDiv.querySelector('button.btn-close').classList.add('d-none');
    },

    _hideErrorMsg: function() {
        const errorMsgDiv = this.el.querySelector('.o_appointment_validation_error');
        errorMsgDiv.classList.add('d-none');
    },

    _showErrorMsg: function(errorMessage) {
        const errorMsgDiv = this.el.querySelector('.o_appointment_validation_error');
        errorMsgDiv.classList.remove('d-none');
        errorMsgDiv.querySelector('.o_appointment_error_text').textContent = errorMessage;
    },

    _validateCheckboxes: function() {
        this.$el.find('.checkbox-group.required').each(function() {
            var checkboxes = $(this).find('.checkbox input');
            checkboxes.prop("required", !checkboxes.some((checkbox) => checkbox.checked));
        });
        if ($(this.$el.find('form'))[0].checkValidity()) {
            return new Promise((resolve, reject) => {});
        }
    },
});
