/** @odoo-module */

import BasicModel from "web.BasicModel";
import { buildSampleORM } from "@web/views/helpers/sample_server";
import { computeVariation } from "@web/core/utils/numbers";
import { Domain } from "@web/core/domain";
import { evaluateExpr } from "@web/core/py_js/py";
import { KeepLast } from "@web/core/utils/concurrency";
import { Model } from "@web/views/helpers/model";

function getPseudoRecords(meta, data) {
    const records = [];
    for (let i = 0; i < meta.domains.length; i++) {
        const record = {};
        for (const [statName, statInfo] of Object.entries(data)) {
            const { values } = statInfo;
            record[statName] = values[i];
        }
        records.push(record);
    }
    return records;
}

function getVariationAsRecords(data) {
    const periods = [];

    Object.entries(data).forEach(([fName, { variations }]) => {
        for (const varIndex in variations) {
            periods[varIndex] = periods[varIndex] || {};
            periods[varIndex][fName] = variations[varIndex];
        }
    });
    return periods;
}

function setupBasicModel(resModel, { getFieldsInfo, postProcessRecord }) {
    const basicModel = new BasicModel();
    const mkDatapoint = basicModel._makeDataPoint;

    const { viewFieldsInfo, fieldsInfo } = getFieldsInfo();

    let legacyModelParams;
    basicModel._makeDataPoint = (params) => {
        params = Object.assign({}, params, legacyModelParams);
        return mkDatapoint.call(basicModel, params);
    };

    return {
        makeRecord: async (params, data) => {
            legacyModelParams = params;
            const recId = await basicModel.makeRecord(resModel, viewFieldsInfo, fieldsInfo);
            const record = basicModel.get(recId);
            postProcessRecord(record, data);
            return record;
        },
        set isSample(bool) {
            basicModel.isSample = bool;
        },
    };
}

export class DashboardModel extends Model {
    setup(params, services) {
        super.setup(...arguments);

        const { orm, user } = services;
        this.orm = orm;
        this.user = user;

        this.keepLast = new KeepLast();

        const { aggregates, fields, formulae, resModel, useSampleModel } = params; // useSampleModel is missing for now
        this.meta = { fields, formulae, resModel, useSampleModel };

        this.meta.aggregates = [];
        for (const agg of aggregates) {
            const enrichedCopy = Object.assign({}, agg);

            const groupOperator = agg.groupOperator || "sum";
            enrichedCopy.measureSpec = `${agg.name}:${groupOperator}(${agg.field})`;

            const field = fields[agg.field];
            enrichedCopy.fieldType = field.type;

            this.meta.aggregates.push(enrichedCopy);
        }

        this.meta.statistics = this.statisticsAsFields();

        this.basicModel = setupBasicModel(this.meta.resModel, {
            getFieldsInfo: () => {
                const legFieldsInfo = {
                    dashboard: {},
                };

                this.meta.aggregates.forEach((agg) => {
                    legFieldsInfo.dashboard[agg.name] = Object.assign({}, agg, {
                        type: agg.fieldType,
                    });
                });

                Object.entries(this.meta.fields).forEach(([fName, f]) => {
                    legFieldsInfo.dashboard[fName] = Object.assign({}, f);
                });

                let formulaId = 1;
                this.meta.formulae.forEach((formula) => {
                    const formulaName = formula.name || `formula_${formulaId++}`;
                    const fakeField = Object.assign({}, formula, {
                        type: "float",
                        name: formulaName,
                    });
                    legFieldsInfo.dashboard[formulaName] = fakeField;
                    legFieldsInfo.formulas = Object.assign(legFieldsInfo.formulas || {}, {
                        [formulaName]: fakeField,
                    });
                });
                legFieldsInfo.default = legFieldsInfo.dashboard;
                return { viewFieldsInfo: legFieldsInfo.dashboard, fieldsInfo: legFieldsInfo };
            },
            postProcessRecord: (record, data) => {
                record.context = this.env.searchModel.context;
                record.viewType = "dashboard";

                const pseudoRecords = getPseudoRecords(this.meta, data);
                record.data = pseudoRecords[0];

                if (this.meta.domains.length > 1) {
                    const comparison = this.env.searchModel._getComparison();

                    record.comparisonData = pseudoRecords[1];
                    record.comparisonTimeRange = comparison.comparisonRange;
                    record.timeRange = comparison.range;
                    record.timeRanges = comparison;
                    record.variationData = getVariationAsRecords(data)[0];
                }
            },
        });
    }

    /**
     * @param {Object} searchParams
     */
    async load(searchParams) {
        const meta = Object.assign({}, this.meta, searchParams);
        let { count, data } = await this.keepLast.add(this._load(meta));
        if (meta.useSampleModel && count === 0) {
            const result = await this.keepLast.add(this._load(meta, true));
            data = result.data;
        } else {
            meta.useSampleModel = false;
        }
        this.basicModel.isSample = meta.useSampleModel;
        this.meta = meta;
        this.data = data;

        const legacyParams = {
            domain: meta.domain,
            compare: meta.domains.length > 1,
        };
        this._legacyRecord_ = await this.keepLast.add(
            this.basicModel.makeRecord(legacyParams, data)
        );
    }

    //--------------------------------------------------------------------------
    // Protected
    //--------------------------------------------------------------------------

    /**
     * @protected
     * @param {Object} meta
     * @param {Object} data
     */
    _computeVariations(meta, data) {
        const n = meta.domains.length - 1;
        for (const statInfo of Object.values(data)) {
            const { values } = statInfo;
            statInfo.variations = new Array(n);
            for (let i = 0; i < n; i++) {
                statInfo.variations[i] = computeVariation(values[i], values[i + 1]);
            }
        }
    }

    /**
     * @protected
     * @param {Object} meta
     * @param {Object} data
     */
    _evalFormulae(meta, data) {
        const records = getPseudoRecords(meta, data);
        for (const formula of meta.formulae) {
            const { name, operation } = formula;
            data[name] = {
                values: new Array(meta.domains.length).fill(NaN),
            };
            for (let i = 0; i < meta.domains.length; i++) {
                try {
                    const value = evaluateExpr(operation, { record: records[i] });
                    if (isFinite(value)) {
                        data[name].values[i] = value;
                    }
                } catch (e) {
                    // pass
                }
            }
        }
    }

    /**
     * @protected
     * @param {Object} meta
     * @param {boolean} [sample=false]
     */
    async _load(meta, sample = false) {
        let orm2use;
        if (sample) {
            if (!this.fakeOrm) {
                this.fakeOrm = buildSampleORM(meta.resModel, meta.fields, this.user);
            }
            orm2use = this.fakeOrm;
        } else {
            orm2use = this.orm;
        }

        const domainMapping = {};
        if (meta.useSampleModel && !sample) {
            // force a read_group RPC without domain to determine if there is data to display
            domainMapping["[]"] = [];
        }
        for (const agg of meta.aggregates) {
            const domain = agg.domain || "[]";
            if (domain in domainMapping) {
                domainMapping[domain].push(agg);
            } else {
                domainMapping[domain] = [agg];
            }
        }

        const proms = [];
        const data = {};
        let count = 0;
        for (const [domain, aggregates] of Object.entries(domainMapping)) {
            for (let i = 0; i < meta.domains.length; i++) {
                const { arrayRepr } = meta.domains[i];
                proms.push(
                    orm2use
                        .readGroup(
                            meta.resModel,
                            Domain.and([domain, arrayRepr]).toList(),
                            aggregates.map((agg) => agg.measureSpec),
                            [],
                            { lazy: true },
                            meta.context
                        )
                        .then((groups) => {
                            const group = groups[0];
                            if (domain === "[]") {
                                count += group.__count;
                            }
                            for (const agg of aggregates) {
                                if (!data[agg.name]) {
                                    data[agg.name] = {
                                        values: new Array(meta.domains.length),
                                    };
                                }
                                data[agg.name].values[i] = group[agg.name] || 0;
                            }
                        })
                );
            }
        }
        await Promise.all(proms);

        this._evalFormulae(meta, data);
        this._computeVariations(meta, data);

        return { count, data };
    }

    evalDomain(record, expr) {
        if (!Array.isArray(expr)) {
            return !!expr;
        }
        const domain = new Domain(expr);
        return domain.contains(getPseudoRecords(this.meta, this.data)[0]);
    }

    statisticsAsFields() {
        const fakeFields = {};
        for (const agg of this.meta.aggregates) {
            fakeFields[agg.name] = agg;
        }
        for (const formula of this.meta.formulae) {
            fakeFields[formula.name] = Object.assign({}, formula, { fieldType: "float" });
        }
        return fakeFields;
    }

    getStatisticDescription(statName) {
        return this.meta.statistics[statName];
    }
}
DashboardModel.services = ["orm", "user"];

// TODO:
// comparisons beware of legacy record
// check fakeFields in legacyrecord
