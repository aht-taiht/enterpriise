odoo.define('documents.MockServer', function (require) {
'use strict';

var MockServer = require('web.MockServer');

MockServer.include({
    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     * @private
     */
    _performRpc: function (route) {
        if (route.indexOf('/documents/image') >= 0 ||
            _.contains(['.png', '.jpg'], route.substr(route.length - 4))) {
            return Promise.resolve();
        }
        return this._super.apply(this, arguments);
    },
    /**
     * Mocks the '_get_models' method of the model 'documents.document'.
     *
     * @param {string} model
     * @param {any[]} domain
     */
    _mockGetModels(model, domain) {
        const notAFile = [];
        const notAttached = [];
        const models = [];
        const groups = this._mockReadGroup(model, {
            domain: domain,
            fields: ['res_model'],
            groupby: ['res_model'],
        });
        for (const group of groups) {
            if (!group.res_model) {
                notAFile.push({
                    id: group.res_model,
                    display_name: "Not a file",
                    __count: group.res_model_count,
                });
            } else if (group.res_model === 'documents.document') {
                notAttached.push({
                    id: group.res_model,
                    display_name: "Not attached",
                    __count: group.res_model_count,
                });
            } else {
                const { res_model_name } = this.data['documents.document'].records.find(
                    record => record.res_model === group.res_model
                );
                models.push({
                    id: group.res_model,
                    display_name: res_model_name,
                    __count: group.res_model_count,
                });
            }
        }
        const sorted = models.sort(({ display_name: a }, { display_name: b }) => {
            return a > b ? 1 : a < b ? -1 : 0;
        });
        return [...sorted, ...notAttached, ...notAFile];
    },
    /**
     * Override to handle the specific case of model 'documents.document'.
     *
     * @override
     * @private
     */
    _mockSearchPanelSelectRange: function (model, [fieldName], kwargs) {
        if (model === 'documents.document' && fieldName === 'folder_id') {
            const fields = ['display_name', 'description', 'parent_folder_id'];
            const records = this._mockSearchRead('documents.folder', [[], fields], {});

            let localCounters = {};
            if (kwargs.enable_counters) {
                localCounters = this._mockSearchPanelLocalCounters(model, fieldName, kwargs);
            }

            const valuesRange = new Map();
            for (const record of records) {
                record.__count = localCounters[record.id] || 0;
                const value = record.parent_folder_id;
                record.parent_folder_id = value && value[0];
                valuesRange.set(record.id, record);
            }
            if (kwargs.enable_counters) {
                this._mockSearchPanelGlobalCounters(valuesRange, 'parent_folder_id');
            }
            return {
                parent_field: 'parent_folder_id',
                values: [...valuesRange.values()],
            };
        }
        return this._super(...arguments);
    },
    /**
     * Override to handle the specific case of model 'documents.document'.
     *
     * @override
     * @private
     */
    _mockSearchPanelSelectMultiRange: function (model, [fieldName], kwargs) {
        const searchDomain = kwargs.search_domain || [];
        const categoryDomain = kwargs.category_domain || [];
        const filterDomain = kwargs.filter_domain || [];

        if (model === 'documents.document') {
            if (fieldName === 'tag_ids') {
                const folderId = categoryDomain.length ? categoryDomain[0][2] : false;
                if (folderId) {
                    const domain = [
                        ...searchDomain,
                        ...categoryDomain,
                        ...filterDomain,
                        [[fieldName, '!=', false]],
                    ];
                    return this.data['documents.tag'].get_tags(domain, folderId);
                } else {
                    return [];
                }
            } else if (fieldName === 'res_model') {
                let domain = [...searchDomain, ...categoryDomain];
                const modelValues = this._mockGetModels(model, domain);
                if (filterDomain) {
                    domain = [...searchDomain, ...categoryDomain, ...filterDomain];
                    const modelCount = {};
                    for (const { id, __count } of this._mockGetModels(model, domain)) {
                        modelCount[id] = __count;
                    }
                    modelValues.forEach(m => m.__count = modelCount[m.id] || 0);
                }
                return modelValues;
            }
        }
        return this._super(...arguments);
    },
});

});
