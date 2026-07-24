from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class TestProductionSemielaboratePhantomBomType(ModuleTestCase):
    module = 'production_semielaborate'

    @with_transaction()
    def test(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        Template = pool.get('product.template')
        Product = pool.get('product.product')
        ProductBom = pool.get('product.product-production.bom')
        Bom = pool.get('production.bom')
        BomInput = pool.get('production.bom.input')
        BomOutput = pool.get('production.bom.output')
        Production = pool.get('production')

        unit, = Uom.search([('name', '=', 'Unit')], limit=1)
        kilogram, = Uom.search([('name', '=', 'Kilogram')], limit=1)

        final_template, = Template.create([{
                    'name': 'Finished',
                    'type': 'goods',
                    'default_uom': unit.id,
                    'producible': True,
                    }])
        final_product, = Product.create([{
                    'template': final_template.id,
                    }])

        semielaborate_template, = Template.create([{
                    'name': 'Semi',
                    'type': 'goods',
                    'default_uom': kilogram.id,
                    'producible': True,
                    }])
        semielaborate_product, = Product.create([{
                    'template': semielaborate_template.id,
                    }])
        Product.write([semielaborate_product], {
                'is_semielaborate': True,
                })

        raw_template, = Template.create([{
                    'name': 'Raw',
                    'type': 'goods',
                    'default_uom': kilogram.id,
                    }])
        raw_product, = Product.create([{
                    'template': raw_template.id,
                    }])

        normal_bom = Bom(
            name='Semi Normal',
            inputs=[
                BomInput(product=raw_product, quantity=20, unit=kilogram),
            ],
            outputs=[
                BomOutput(product=semielaborate_product, quantity=20,
                    unit=kilogram),
            ])
        normal_bom.save()

        phantom_bom = Bom(
            name='Semi Phantom',
            phantom=True,
            phantom_unit=kilogram,
            phantom_quantity=20,
            inputs=[
                BomInput(product=raw_product, quantity=20, unit=kilogram),
            ])
        phantom_bom.save()

        semielaborate_product.boms = [
            ProductBom(product=semielaborate_product, sequence=1, bom=phantom_bom,
                bom_type='phantom'),
            ProductBom(product=semielaborate_product, sequence=2, bom=normal_bom,
                bom_type='normal'),
            ]
        semielaborate_product.save()

        final_bom = Bom(
            name='Finished BOM',
            inputs=[
                BomInput(phantom_bom=phantom_bom, quantity=20, unit=kilogram),
            ],
            outputs=[
                BomOutput(product=final_product, quantity=100, unit=unit),
            ])
        final_bom.save()
        final_product.boms = [
            ProductBom(product=final_product, sequence=1, bom=final_bom,
                bom_type='normal'),
            ]
        final_product.save()

        linked_boms = ProductBom.search([
                ('bom', '=', phantom_bom.id),
                ('bom_type', '=', 'phantom'),
                ])
        self.assertEqual([b.product.id for b in linked_boms],
            [semielaborate_product.id])
        self.assertEqual(Bom.search([
                ('inputs.phantom_bom', '=', phantom_bom.id),
                ]), [final_bom])
        self.assertEqual(semielaborate_product.get_bom().bom, normal_bom)
        self.assertEqual(
            final_template.get_semielaborate_products('semielaborate_products'),
            [semielaborate_product.id])
        self.assertEqual(
            semielaborate_template.get_final_products('final_products'),
            [final_product.id])

        production = Production()
        production.product = final_product
        production.bom = final_bom
        production.unit = unit
        production.quantity = 100

        self.assertEqual(
            production.on_change_with_semielaborate_multiple(), 1)
        production.explode_bom()
        self.assertEqual(len(production.inputs), 1)
        self.assertEqual(production.inputs[0].product, raw_product)
        self.assertEqual(production.inputs[0].quantity, 20)


del ModuleTestCase
