# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from decimal import Decimal

from trytond.model import dualmethod, fields
from trytond.modules.product import round_price
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
        return bool(self.bom and any(self._semielaborate_inputs()))

    def _semielaborate_inputs(self):
        ProductBom = Pool().get('product.product-production.bom')

        for input_ in self.bom.inputs:
            if (input_.product and input_.product.template
                    and input_.product.template.is_semielaborate):
                yield input_.product

            if not input_.phantom_bom:
                continue

            linked_boms = ProductBom.search([
                    ('bom', '=', input_.phantom_bom.id),
                    ('bom_type', '=', 'phantom'),
                    ])
            for linked_bom in linked_boms:
                product = linked_bom.product
                if (product and product.template
                        and product.template.is_semielaborate):
                    yield product

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

    @staticmethod
    def _is_phantom_product(product):
        if not product or 'phantom' not in product.__class__._fields:
            return False
        try:
            return bool(product.phantom)
        except AttributeError:
            return False

    @classmethod
    def _explode_phantom_inputs(cls, production, inputs):
        new_inputs = []
        for move in inputs:
            product = move.product
            if not cls._is_phantom_product(product) or not product.boms:
                new_inputs.append(move)
                continue
            bom = product.boms[0].bom
            factor = bom.compute_factor(product, move.quantity, move.unit)
            for input_ in bom.inputs:
                quantity = input_.compute_quantity(factor)
                new_move = production._move(
                    'input', input_.product, input_.unit, quantity)
                if new_move:
                    new_inputs.append(new_move)
        return new_inputs

    @fields.depends(
        'company', 'location', 'bom', 'product', 'unit', 'quantity',
        'inputs', 'outputs', methods=['_move'])
    def explode_bom(self):
        super().explode_bom()
        if not (self.bom and self.product and self.unit):
            return
        self.inputs = self._explode_phantom_inputs(self, self.inputs or [])
        Uom = Pool().get('product.uom')
        factor = self.bom.compute_factor(
            self.product, self.quantity or 0, self.unit)
        for input_ in self.bom.inputs:
            if not input_.product:
                continue
            quantity = input_.compute_quantity(factor)
            default_uom = self._get_product_default_uom(input_.product)
            if default_uom:
                Uom.compute_qty(
                    input_.unit, quantity, default_uom, round=False)

    @dualmethod
    def set_moves(cls, productions):
        Move = Pool().get('stock.move')

        super(Production, cls).set_moves(productions)
        for production in productions:
            to_delete = []
            cost = Decimal(0)
            for move in production.inputs:
                product = move.product
                if not cls._is_phantom_product(product) or not product.boms:
                    cost += (Decimal(str(move.internal_quantity))
                        * product.cost_price)
                    continue
                to_delete.append(move)
                bom = product.boms[0].bom
                factor = bom.compute_factor(product, move.quantity, move.unit)
                for input_ in bom.inputs:
                    quantity = input_.compute_quantity(factor)
                    product = input_.product
                    new_move = production._move(
                        'input', product, input_.unit, quantity)
                    if new_move:
                        new_move.production_input = production
                        new_move.planned_date = production.planned_date
                        new_move.save()
                        cost += Decimal(str(quantity)) * product.cost_price
            if to_delete:
                for output in production.outputs:
                    if output.product == production.product:
                        output.unit_price = round_price(
                            cost / Decimal(str(output.internal_quantity)))
                        output.save()
                Move.delete(to_delete)

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
