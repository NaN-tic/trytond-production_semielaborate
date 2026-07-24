# This file is part of Tryton. The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.tests.test_tryton import (
    ModuleTestCase, activate_module, with_transaction)


class ProductionSemielaborateTestCase(ModuleTestCase):
    'Test ProductionSemielaborate module'
    module = 'production_semielaborate'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        activate_module('production_phantom')

    @with_transaction()
    def test_get_semielaborate_products_from_bom_inputs(self):
        'Template returns semielaborate products used in BOM inputs'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        ProductBom = pool.get('product.product-production.bom')
        Bom = pool.get('production.bom')

        unit, = Uom.search([('name', '=', 'Unit')], limit=1)

        template = Template.create([{
                    'name': 'Finished',
                    'type': 'goods',
                    'default_uom': unit.id,
                    'producible': True,
                    }])[0]
        product, = Product.create([{
                    'template': template.id,
                    'phantom': False,
                    }])

        semielaborate_template = Template.create([{
                    'name': 'Semi',
                    'type': 'goods',
                    'default_uom': unit.id,
                    'producible': True,
                    }])[0]
        semielaborate_product, = Product.create([{
                    'template': semielaborate_template.id,
                    'phantom': False,
                    }])
        Product.write([semielaborate_product], {
                'is_semielaborate': True,
                })

        raw_template = Template.create([{
                    'name': 'Raw',
                    'type': 'goods',
                    'default_uom': unit.id,
                    }])[0]
        raw_product, = Product.create([{
                    'template': raw_template.id,
                    'phantom': False,
                    }])

        bom, = Bom.create([{
                    'name': 'BOM Finished',
                    'phantom': False,
                    'inputs': [('create', [{
                                    'product': semielaborate_product.id,
                                    'phantom_bom': None,
                                    'quantity': 1,
                                    'unit': unit.id,
                                    }, {
                                    'product': raw_product.id,
                                    'phantom_bom': None,
                                    'quantity': 1,
                                    'unit': unit.id,
                                    }])],
                    'outputs': [('create', [{
                                    'product': product.id,
                                    'phantom_bom': None,
                                    'quantity': 1,
                                    'unit': unit.id,
                                    }])],
                    }])
        ProductBom.create([{
                    'product': product.id,
                    'sequence': 1,
                    'bom': bom.id,
                    }])

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

        Bom.create([{
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

        self.assertEqual(
            semielaborate_template.get_final_products('final_products'),
            [final_product.id])
        self.assertEqual(
            Product.search([
                    ('bom_outputs.bom.inputs.product.template', 'in',
                        [semielaborate_template.id]),
                    ]),
            [final_product])
        self.assertEqual(
            Product.search([
                    ('bom_outputs.bom.inputs.product', 'in',
                        [semielaborate_product.id]),
                    ]),
            [final_product])

    @with_transaction()
    def test_production_semielaborate_multiple(self):
        'Production syncs semielaborate multiple with quantity'
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
        final_product = Product(template=final_template, phantom=False)

        semielaborate_template = Template(
            name='Semi',
            type='goods',
            default_uom=kilogram,
            producible=True,
            is_semielaborate=True)
        semielaborate_product = Product(
            template=semielaborate_template, phantom=False)

        bom = Bom(
            name='BOM Finished',
            phantom=False,
            inputs=[
                BomInput(
                    product=semielaborate_product, phantom_bom=None,
                    quantity=20, unit=kilogram),
            ],
            outputs=[BomOutput(product=final_product, phantom_bom=None,
                quantity=100, unit=unit)])

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

        production.semielaborate_multiple = 3
        production.on_change_semielaborate_multiple()
        self.assertEqual(production.quantity, 300)
        self.assertEqual(production.semielaborate_multiple, 3)
        self.assertEqual(len(production.inputs), 1)
        self.assertEqual(len(production.outputs), 1)
        self.assertEqual(production.inputs[0].quantity, 60)
        self.assertEqual(production.outputs[0].quantity, 300)

    @with_transaction()
    def test_phantom_bom_can_be_linked_without_output_product(self):
        'Semielaborate allows linking phantom BOMs without output product'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Bom = pool.get('production.bom')
        BomInput = pool.get('production.bom.input')
        ProductBom = pool.get('product.product-production.bom')

        unit, = Uom.search([('name', '=', 'Unit')], limit=1)

        raw_template = Template(name='Raw Link', type='goods', default_uom=unit)
        raw_product = Product(template=raw_template, phantom=False)

        semielaborate_template = Template(
            name='Semi Link',
            type='goods',
            default_uom=unit,
            producible=True,
            is_semielaborate=True)
        semielaborate_product = Product(
            template=semielaborate_template, phantom=False)

        phantom_bom = Bom(
            name='Phantom Link BOM',
            phantom=True,
            phantom_unit=unit,
            phantom_quantity=1,
            inputs=[BomInput(
                product=raw_product, phantom_bom=None, quantity=2, unit=unit)])

        product_bom = ProductBom(
            product=semielaborate_product,
            bom=phantom_bom,
            bom_type='phantom')
        ProductBom.save([product_bom])

        self.assertEqual(product_bom.bom, phantom_bom)

    @with_transaction()
    def test_explode_bom_expands_phantom_inputs(self):
        'Production explodes phantom products with semielaborate active'
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        Bom = pool.get('production.bom')
        BomInput = pool.get('production.bom.input')
        BomOutput = pool.get('production.bom.output')
        ProductBom = pool.get('product.product-production.bom')
        Production = pool.get('production')

        if 'phantom' not in Product._fields:
            self.skipTest('production_phantom field not active in test DB')

        unit, = Uom.search([('name', '=', 'Unit')], limit=1)

        raw_template = Template(
            name='Raw',
            type='goods',
            default_uom=unit)
        raw_product = Product(template=raw_template)

        phantom_template = Template(
            name='Phantom Semi',
            type='goods',
            default_uom=unit,
            producible=True,
            is_semielaborate=True)
        phantom_product = Product(template=phantom_template, phantom=True)

        final_template = Template(
            name='Finished',
            type='goods',
            default_uom=unit,
            producible=True)
        final_product = Product(template=final_template)

        phantom_bom = Bom(
            name='BOM Phantom',
            phantom=False,
            inputs=[BomInput(
                product=raw_product, phantom_bom=None, quantity=2, unit=unit)],
            outputs=[BomOutput(
                product=phantom_product, phantom_bom=None,
                quantity=1, unit=unit)])
        phantom_product.boms = [
            ProductBom(product=phantom_product, sequence=1, bom=phantom_bom)]

        final_bom = Bom(
            name='BOM Finished',
            phantom=False,
            inputs=[BomInput(
                product=phantom_product, phantom_bom=None,
                quantity=3, unit=unit)],
            outputs=[BomOutput(
                product=final_product, phantom_bom=None,
                quantity=1, unit=unit)])
        final_product.boms = [
            ProductBom(product=final_product, sequence=1, bom=final_bom)]

        production = Production()
        production.product = final_product
        production.bom = final_bom
        production.unit = unit
        production.quantity = 1

        production.explode_bom()

        self.assertEqual(len(production.inputs), 1)
        self.assertEqual(production.inputs[0].product, raw_product)
        self.assertEqual(production.inputs[0].quantity, 6)


del ModuleTestCase
