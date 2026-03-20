# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    is_semielaborate = fields.Boolean('Semielaborate')
    semielaborate_products = fields.Function(
        fields.Many2Many(
            'product.product', None, None, 'Semielaborates',
            help='Semielaborate products found in the BOM definition.',
            states={
                'invisible': Eval('is_semielaborate', False),
                },
            depends=['is_semielaborate']),
        'get_semielaborate_products')
    final_products = fields.Function(
        fields.Many2Many(
            'product.product', None, None, 'Final Products',
            help='Final products that use this semielaborate in their BOM.',
            states={
                'invisible': ~Eval('is_semielaborate', False),
                },
            depends=['is_semielaborate']),
        'get_final_products')

    def get_semielaborate_products(self, name):
        product_ids = set()
        for product in self.products:
            for product_bom in product.boms:
                if not product_bom.bom:
                    continue
                for input_ in product_bom.bom.inputs:
                    template = input_.product.template if input_.product else None
                    if (template
                            and getattr(template, 'is_semielaborate', False)):
                        product_ids.add(input_.product.id)
        return list(sorted(product_ids))

    def get_final_products(self, name):
        pool = Pool()
        Bom = pool.get('production.bom')

        variant_ids = [p.id for p in self.products if p.id]
        if not variant_ids:
            return []

        boms = Bom.search([('inputs.product', 'in', variant_ids)])
        product_ids = set()
        for bom in boms:
            for output in bom.outputs:
                if output.product:
                    product_ids.add(output.product.id)

        return list(sorted(product_ids))

class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    is_semielaborate = fields.Function(
        fields.Boolean('Semielaborate'), 'get_is_semielaborate',
        setter='set_is_semielaborate')
    semielaborate_products = fields.Function(
        fields.Many2Many(
            'product.product', None, None, 'Semielaborates',
            states={
                'invisible': Eval('is_semielaborate', False),
                },
            depends=['is_semielaborate']),
        'get_semielaborate_products')
    final_products = fields.Function(
        fields.Many2Many(
            'product.product', None, None, 'Final Products',
            states={
                'invisible': ~Eval('is_semielaborate', False),
                },
            depends=['is_semielaborate']),
        'get_final_products')

    def get_is_semielaborate(self, name):
        return bool(self.template and self.template.is_semielaborate)

    @classmethod
    def set_is_semielaborate(cls, products, name, value):
        Template = Pool().get('product.template')
        templates = list({p.template for p in products if p.template})
        if templates:
            Template.write(templates, {
                    'is_semielaborate': value,
                    })

    def get_semielaborate_products(self, name):
        if self.template:
            return self.template.get_semielaborate_products(name)
        return []

    def get_final_products(self, name):
        if self.template:
            return self.template.get_final_products(name)
        return []
