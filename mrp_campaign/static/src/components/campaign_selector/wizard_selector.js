import {registry} from "@web/core/registry";
import {Component, useRef, useState, useEffect} from "@odoo/owl";
import {useDebounced} from "@web/core/utils/timing";

export class WizardSelector extends Component {
    static template = "mrp_campaign.WizardSelector";

    setup() {
        this.availableList = useState({items: []});
        this.selectedList = useState({items: []});
        this._displayedAvailable = useState({items: []});
        this._displayedSelected = useState({items: []});

        useEffect(
            (availableLines) => {
                if (availableLines !== undefined) {
                    this._loadData(availableLines);
                }
                return () => {};
            },
            () => [this.props.record.data[this.props.name]]
        );

        this.searchAvailable = useRef("search-available");
        this.searchSelected = useRef("search-selected");

        this.debouncedSave = useDebounced(this._saveSelected.bind(this), 300);
    }

    get availableItems() {
        return this.availableList.items;
    }

    get selectedItems() {
        return this.selectedList.items;
    }

    get hasAvailable() {
        return this.availableList.items.length > 0;
    }

    get hasSelected() {
        return this.selectedList.items.length > 0;
    }

    get hasAnyItems() {
        return this.hasAvailable || this.hasSelected;
    }

    get displayedAvailable() {
        return this._displayedAvailable.items;
    }

    get displayedSelected() {
        return this._displayedSelected.items;
    }

    formatDate(dateStr) {
        if (!dateStr) {
            return "";
        }
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString();
        } catch {
            return dateStr;
        }
    }

    _loadData(data) {
        if (data) {
            try {
                const parsed = JSON.parse(data);
                if (!parsed || !Array.isArray(parsed)) {
                    this.availableList.items = [];
                    this._displayedAvailable.items = [];
                    this.selectedList.items = [];
                    this._displayedSelected.items = [];
                    return;
                }
                const selectedIds = this._getSelectedIds();
                const selectedItems = parsed.filter((item) =>
                    selectedIds.includes(item.id)
                );
                const availableItems = parsed.filter(
                    (item) => !selectedIds.includes(item.id)
                );

                this.availableList.items = availableItems;
                this._displayedAvailable.items = [...availableItems];
                this.selectedList.items = selectedItems;
                this._displayedSelected.items = [...selectedItems];
            } catch (e) {
                console.error("Failed to parse available lines:", e);
            }
        } else {
            this.availableList.items = [];
            this._displayedAvailable.items = [];
            this.selectedList.items = [];
            this._displayedSelected.items = [];
        }
    }

    _getSelectedIds() {
        try {
            const selectedData = this.props.record.data.selected_line_ids;
            return selectedData ? JSON.parse(selectedData) : [];
        } catch {
            return [];
        }
    }

    _saveSelected() {
        const ids = this.selectedList.items.map((item) => item.id);
        this.props.record.update(
            {selected_line_ids: JSON.stringify(ids)},
            {save: true}
        );
    }

    addToSelected(item) {
        this.availableList.items = this.availableList.items.filter(
            (i) => i.id !== item.id
        );
        this._displayedAvailable.items = [...this.availableList.items];
        this.selectedList.items = [...this.selectedList.items, item];
        this._displayedSelected.items = [...this.selectedList.items];
        this.debouncedSave();
        if (this.searchAvailable.el) {
            this.searchAvailable.el.value = "";
        }
    }

    removeFromSelected(item) {
        this.selectedList.items = this.selectedList.items.filter(
            (i) => i.id !== item.id
        );
        this._displayedSelected.items = [...this.selectedList.items];
        this.availableList.items = [...this.availableList.items, item];
        this.availableList.items.sort((a, b) => a.name.localeCompare(b.name));
        this._displayedAvailable.items = [...this.availableList.items];
        this.debouncedSave();
        if (this.searchSelected.el) {
            this.searchSelected.el.value = "";
        }
    }

    addAllToSelected() {
        this.selectedList.items = [
            ...this.selectedList.items,
            ...this.availableList.items,
        ];
        this._displayedSelected.items = [...this.selectedList.items];
        this.availableList.items = [];
        this._displayedAvailable.items = [];
        this.debouncedSave();
    }

    removeAllFromSelected() {
        this.availableList.items = [
            ...this.availableList.items,
            ...this.selectedList.items,
        ];
        this.availableList.items.sort((a, b) => a.name.localeCompare(b.name));
        this._displayedAvailable.items = [...this.availableList.items];
        this.selectedList.items = [];
        this._displayedSelected.items = [];
        this.debouncedSave();
    }

    filterAvailable() {
        const searchTerm = this.searchAvailable.el?.value.toLowerCase() || "";
        if (!searchTerm) {
            this._displayedAvailable.items = [...this.availableList.items];
        } else {
            this._displayedAvailable.items = this.availableList.items.filter((item) =>
                this.matchesSearch(item, searchTerm)
            );
        }
    }

    filterSelected() {
        const searchTerm = this.searchSelected.el?.value.toLowerCase() || "";
        if (!searchTerm) {
            this._displayedSelected.items = [...this.selectedList.items];
        } else {
            this._displayedSelected.items = this.selectedList.items.filter((item) =>
                this.matchesSearch(item, searchTerm)
            );
        }
    }

    matchesSearch(item, searchTerm) {
        return (
            (item.name && item.name.toLowerCase().includes(searchTerm)) ||
            (item.additional_ref &&
                item.additional_ref.toLowerCase().includes(searchTerm)) ||
            String(item.qty).includes(searchTerm)
        );
    }
}

export const wizardSelectorField = {
    component: WizardSelector,
    supportedTypes: ["char"],
};

registry.category("fields").add("wizard_selector", wizardSelectorField);
