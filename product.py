# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, Get, If


BOM_TYPES = [
    ('normal', 'Normal'),
    ('phantom', 'Phantom'),
]


def search_semielaborate_products_domain(prefix, name, clause):
    target = prefix
    if name.startswith('semielaborate_products.'):
        target += name[len('semielaborate_products'):]
    return [
        (prefix + '.template.is_semielaborate', '=', True),
        (target,) + tuple(clause[1:]),
        ]


def _iter_semielaborate_products_from_bom(bom):
    Product = Pool().get('product.product')
    ProductBom = Pool().get('product.product-production.bom')

    for input_ in bom.inputs:
        if input_.product is not None:
            product = Product(input_.product.id)
            template = product.template if product else None
            if template and getattr(template, 'is_semielaborate', False):
                yield product

        if input_.phantom_bom is None:
            continue

        linked_boms = ProductBom.search([
                ('bom', '=', input_.phantom_bom.id),
                ('bom_type', '=', 'phantom'),
                ])
        for linked_bom in linked_boms:
            if linked_bom.product is None:
                continue
            product = Product(linked_bom.product.id)
            if product is None or product.template is None:
                continue
            if getattr(product.template, 'is_semielaborate', False):
                yield product


def _get_semielaborate_product_ids_for_bom(bom):
    Product = Pool().get('product.product')
    ProductBom = Pool().get('product.product-production.bom')

    product_ids = {
        product.id for product in _iter_semielaborate_products_from_bom(bom)
    }
    phantom_bom_ids = [
        input_.phantom_bom.id for input_ in bom.inputs
        if input_.phantom_bom is not None
    ]
    if phantom_bom_ids:
        for phantom_bom_id in phantom_bom_ids:
            linked_boms = ProductBom.search([
                    ('bom', '=', phantom_bom_id),
                    ('bom_type', '=', 'phantom'),
                    ])
            for linked_bom in linked_boms:
                if linked_bom.product is None:
                    continue
                product = Product(linked_bom.product.id)
                if (product and product.template
                        and product.template.is_semielaborate):
                    product_ids.add(product.id)
    return product_ids


def _search_semielaborate_products_from_phantom(cls, name, clause):
    ProductBom = Pool().get('product.product-production.bom')

    if name != 'semielaborate_products':
        return []

    _, operator, operand, *extra = clause
    if operator == 'in':
        product_domain = [('id', 'in', operand)]
    elif operator == '=':
        product_domain = [('id', '=', operand)]
    else:
        return []

    semielaborate_products = cls.search([
            ('template.is_semielaborate', '=', True),
            product_domain[0],
            ] + extra)
    if not semielaborate_products:
        return []

    linked_boms = ProductBom.search([
            ('product', 'in', [p.id for p in semielaborate_products]),
            ('bom_type', '=', 'phantom'),
            ])
    if not linked_boms:
        return []

    final_products = cls.search([
            ('bom_outputs.bom.inputs.phantom_bom', 'in',
                [b.bom.id for b in linked_boms]),
            ])
    return [p.id for p in final_products]


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
        'get_semielaborate_products',
        searcher='search_semielaborate_products')
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
        ProductBom = Pool().get('product.product-production.bom')
        product_ids = set()
        product_boms = ProductBom.search([
                ('product.template', '=', self.id),
                ('bom_type', '!=', 'phantom'),
                ])
        for product_bom in product_boms:
            if not product_bom.bom:
                continue
            product_ids.update(
                _get_semielaborate_product_ids_for_bom(product_bom.bom))
        return list(sorted(product_ids))

    @classmethod
    def search_semielaborate_products(cls, name, clause):
        pool = Pool()
        Product = pool.get('product.product')

        product_ids = _search_semielaborate_products_from_phantom(
            Product, name, clause)
        if not product_ids:
            return search_semielaborate_products_domain(
                'products.bom_outputs.bom.inputs.product', name, clause)
        return ['OR',
            search_semielaborate_products_domain(
                'products.bom_outputs.bom.inputs.product', name, clause),
            ('products', 'in', product_ids),
            ]

    def get_final_products(self, name):
        pool = Pool()
        Bom = pool.get('production.bom')
        Product = pool.get('product.product')

        variant_ids = [p.id for p in Product.search([('template', '=', self.id)])]
        if not variant_ids:
            return []

        boms = list(Bom.search([('inputs.product', 'in', variant_ids)]))
        ProductBom = pool.get('product.product-production.bom')
        linked_boms = ProductBom.search([
                ('product.template', '=', self.id),
                ('bom_type', '=', 'phantom'),
                ])
        if linked_boms:
            for linked_bom in linked_boms:
                boms.extend(Bom.search([
                            ('inputs.phantom_bom', '=', linked_bom.bom.id),
                            ]))
        product_ids = set()
        for bom in boms:
            for output in bom.outputs:
                if output.product:
                    product_ids.add(output.product.id)

        return list(sorted(product_ids))

class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    bom_outputs = fields.One2Many(
        'production.bom.output', 'product', 'BOM Outputs')
    is_semielaborate = fields.Function(
        fields.Boolean('Semielaborate'), 'get_is_semielaborate',
        setter='set_is_semielaborate', searcher='search_is_semielaborate')
    semielaborate_products = fields.Function(
        fields.Many2Many(
            'product.product', None, None, 'Semielaborates',
            states={
                'invisible': Eval('is_semielaborate', False),
                },
            depends=['is_semielaborate']),
        'get_semielaborate_products',
        searcher='search_semielaborate_products')
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

    def check_bom_recursion(self, product=None):
        if product is None:
            product = self
        for product_bom in self.boms:
            if getattr(product_bom, 'bom_type', 'normal') == 'phantom':
                continue
            for input_ in product_bom.bom.inputs:
                if input_.phantom_bom:
                    for line in input_.phantom_bom.inputs:
                        line.check_bom_recursion()
                if input_.product and (input_.product == product
                        or input_.product.check_bom_recursion(
                            product=product)):
                    from trytond.i18n import gettext
                    from trytond.model.exceptions import RecursionError
                    raise RecursionError(gettext(
                            'production.msg_recursive_bom_product',
                            product=product.rec_name))

    def get_bom(self, pattern=None):
        if pattern is None:
            pattern = {}
        for bom in self.boms:
            if getattr(bom, 'bom_type', 'normal') == 'phantom':
                continue
            if bom.match(pattern):
                return bom

    @classmethod
    def search_is_semielaborate(cls, name, clause):
        return [('template.is_semielaborate',) + tuple(clause[1:])]

    @classmethod
    def search_semielaborate_products(cls, name, clause):
        product_ids = _search_semielaborate_products_from_phantom(
            cls, name, clause)
        if not product_ids:
            return search_semielaborate_products_domain(
                'bom_outputs.bom.inputs.product', name, clause)
        return ['OR',
            search_semielaborate_products_domain(
                'bom_outputs.bom.inputs.product', name, clause),
            ('id', 'in', product_ids),
            ]

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


class ProductBom(metaclass=PoolMeta):
    __name__ = 'product.product-production.bom'

    bom_type = fields.Selection(BOM_TYPES, 'Type', required=True, sort=False)

    @staticmethod
    def default_bom_type():
        return 'normal'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        product_id = If(Bool(Eval('product')),
            Eval('product', 0),
            Get(Eval('_parent_product', {}), 'id', 0))
        cls.bom.domain = [
            If(Eval('bom_type', 'normal') == 'phantom',
                ('phantom', '=', True),
                ('phantom', '!=', True)),
            If(Eval('bom_type', 'normal') == 'phantom',
                (),
                ('output_products', '=', product_id)),
            ]
