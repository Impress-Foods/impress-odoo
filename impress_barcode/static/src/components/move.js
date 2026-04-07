/** @odoo-module **/

import {Component} from "@odoo/owl";
import {registry} from "@web/core/registry";

export default class MoveComponent extends Component {
    get move() {
        return this.props.move;
    }
}
MoveComponent.props = ["move"];
MoveComponent.template = "impress_barcode.MoveComponent";
registry.category("components").add("MoveComponent", MoveComponent);
