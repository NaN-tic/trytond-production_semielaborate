# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    semielaborate_multiple = fields.Float(
        'Semielaborate Multiple',
        states={
            'readonly': ~Eval('state').in_(['request', 'draft']),
            'invisible': ~Eval('product'),
            },
        depends=['state', 'product'])

    @fields.depends('bom', 'product', 'quantity', 'unit')
    def on_change_with_semielaborate_multiple(self, name=None):
        output_quantity = self._get_semielaborate_output_quantity()
        if not output_quantity:
            return 0.0
        return (self.quantity or 0.0) / output_quantity

    def _has_semielaborate_input(self):
        return bool(self.bom and any(
            i.product and i.product.template
            and i.product.template.is_semielaborate
            for i in self.bom.inputs))

    def _get_semielaborate_output_quantity(self):
        if not (self._has_semielaborate_input()
                and self.bom and self.product and self.unit):
            return 0.0
        Uom = Pool().get('product.uom')
        output_quantity = 0.0
        for output in self.bom.outputs:
            if output.product == self.product:
                output_quantity += Uom.compute_qty(
                    output.unit, output.quantity, self.unit, round=False)
        return output_quantity

    def _get_product_default_uom(self, product):
        if product and product.template:
            return product.template.default_uom

    @fields.depends(
        'company', 'location', 'bom', 'product', 'unit', 'quantity',
        'inputs', 'outputs', methods=['_move'])
    def explode_bom(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        if not (self.bom and self.product and self.unit):
            return

        factor = self.bom.compute_factor(
            self.product, self.quantity or 0, self.unit)
        inputs = []
        for input_ in self.bom.inputs:
            quantity = input_.compute_quantity(factor)
            move = self._move('input', input_.product, input_.unit, quantity)
            if move:
                inputs.append(move)
                default_uom = self._get_product_default_uom(input_.product)
                if default_uom:
                    Uom.compute_qty(
                        input_.unit, quantity, default_uom, round=False)
        self.inputs = inputs

        outputs = []
        for output in self.bom.outputs:
            quantity = output.compute_quantity(factor)
            move = self._move('output', output.product, output.unit, quantity)
            if move:
                outputs.append(move)
        self.outputs = outputs

    @fields.depends(
        'semielaborate_multiple', 'bom', 'product', 'quantity', 'unit',
        methods=['explode_bom'])
    def on_change_semielaborate_multiple(self):
        output_quantity = self._get_semielaborate_output_quantity()
        if not output_quantity:
            return
        self.quantity = (
            (self.semielaborate_multiple or 0.0) * output_quantity)
        self.explode_bom()

    @fields.depends(
        'bom', 'product', 'quantity', 'unit', 'semielaborate_multiple',
        methods=['explode_bom'])
    def on_change_bom(self):
        super().on_change_bom()
        self.semielaborate_multiple = (
            self.on_change_with_semielaborate_multiple())

    @fields.depends(
        'product', 'unit', 'semielaborate_multiple',
        methods=['explode_bom', 'set_planned_start_date'])
    def on_change_product(self):
        super().on_change_product()
        self.semielaborate_multiple = (
            self.on_change_with_semielaborate_multiple())

    @fields.depends('unit', 'semielaborate_multiple', methods=['explode_bom'])
    def on_change_unit(self):
        super().on_change_unit()
        self.semielaborate_multiple = (
            self.on_change_with_semielaborate_multiple())

    @fields.depends(
        'bom', 'product', 'quantity', 'unit', 'semielaborate_multiple',
        methods=['explode_bom'])
    def on_change_quantity(self):
        super().on_change_quantity()
        self.semielaborate_multiple = (
            self.on_change_with_semielaborate_multiple())
