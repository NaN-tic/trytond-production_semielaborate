# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    semielaborate_multiple = fields.Function(
        fields.Float('Semielaborate Multiple', readonly=True),
        'on_change_with_semielaborate_multiple')

    @fields.depends('bom', 'product', 'quantity', 'unit')
    def on_change_with_semielaborate_multiple(self, name=None):
        if not (self.bom and self.product and self.quantity and self.unit):
            return 0.0
        if not any(
                i.product and i.product.template
                and i.product.template.is_semielaborate
                for i in self.bom.inputs):
            return 0.0
        return self.bom.compute_factor(self.product, self.quantity, self.unit)
