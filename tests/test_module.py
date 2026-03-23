# This file is part of Tryton. The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class ProductionSemielaborateTestCase(ModuleTestCase):
    'Test ProductionSemielaborate module'
    module = 'production_semielaborate'

    @with_transaction()
    def test_get_semielaborate_products_from_bom_inputs(self):
        'Template returns semielaborate products used in BOM inputs'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        ProductBom = pool.get('product.product-production.bom')
        Bom = pool.get('production.bom')
        BomInput = pool.get('production.bom.input')
        BomOutput = pool.get('production.bom.output')

        unit, = Uom.search([('name', '=', 'Unit')], limit=1)

        template = Template(
            name='Finished',
            type='goods',
            default_uom=unit,
            producible=True)
        product = Product(template=template)

        semielaborate_template = Template(
            name='Semi',
            type='goods',
            default_uom=unit,
            is_semielaborate=True)
        semielaborate_product = Product(template=semielaborate_template)

        raw_template = Template(
            name='Raw',
            type='goods',
            default_uom=unit)
        raw_product = Product(template=raw_template)

        bom = Bom(
            name='BOM Finished',
            inputs=[
                BomInput(product=semielaborate_product, quantity=1, unit=unit),
                BomInput(product=raw_product, quantity=1, unit=unit),
            ],
            outputs=[BomOutput(product=product, quantity=1, unit=unit)])
        product.boms = [ProductBom(product=product, sequence=1, bom=bom)]
        template.products = [product]

        self.assertEqual(
            template.get_semielaborate_products('semielaborate_products'),
            [semielaborate_product.id])

    @with_transaction()
    def test_get_final_products_from_semielaborate(self):
        'Template returns final products that use the semielaborate'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        ProductBom = pool.get('product.product-production.bom')
        Bom = pool.get('production.bom')

        unit, = Uom.search([('name', '=', 'Unit')], limit=1)

        semielaborate_template = Template.create([{
                    'name': 'Semi',
                    'type': 'goods',
                    'default_uom': unit.id,
                    'producible': True,
                    'is_semielaborate': True,
                    }])[0]
        semielaborate_product, = Product.create([{
                    'template': semielaborate_template.id,
                    }])

        final_template = Template.create([{
                    'name': 'Finished',
                    'type': 'goods',
                    'default_uom': unit.id,
                    'producible': True,
                    }])[0]
        final_product, = Product.create([{
                    'template': final_template.id,
                    }])

        bom, = Bom.create([{
                    'name': 'BOM Finished',
                    'inputs': [('create', [{
                                    'product': semielaborate_product.id,
                                    'quantity': 1,
                                    'unit': unit.id,
                                    }])],
                    'outputs': [('create', [{
                                    'product': final_product.id,
                                    'quantity': 1,
                                    'unit': unit.id,
                                    }])],
                    }])
        ProductBom.create([{
                    'product': final_product.id,
                    'sequence': 1,
                    'bom': bom.id,
                    }])

        self.assertEqual(
            semielaborate_template.get_final_products('final_products'),
            [final_product.id])

    @with_transaction()
    def test_production_semielaborate_multiple(self):
        'Production calculates the semielaborate multiple from BOM factor'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Bom = pool.get('production.bom')
        BomInput = pool.get('production.bom.input')
        BomOutput = pool.get('production.bom.output')
        Production = pool.get('production')

        unit, = Uom.search([('name', '=', 'Unit')], limit=1)
        kilogram, = Uom.search([('name', '=', 'Kilogram')], limit=1)

        final_template = Template(
            name='Finished',
            type='goods',
            default_uom=unit,
            producible=True)
        final_product = Product(template=final_template)

        semielaborate_template = Template(
            name='Semi',
            type='goods',
            default_uom=kilogram,
            producible=True,
            is_semielaborate=True)
        semielaborate_product = Product(template=semielaborate_template)

        bom = Bom(
            name='BOM Finished',
            inputs=[
                BomInput(
                    product=semielaborate_product, quantity=20, unit=kilogram),
            ],
            outputs=[BomOutput(product=final_product, quantity=100, unit=unit)])

        production = Production()
        production.product = final_product
        production.bom = bom
        production.unit = unit

        production.quantity = 100
        self.assertEqual(
            production.on_change_with_semielaborate_multiple(), 1)

        production.quantity = 200
        self.assertEqual(
            production.on_change_with_semielaborate_multiple(), 2)


del ModuleTestCase
