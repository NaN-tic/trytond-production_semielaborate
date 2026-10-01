import unittest

from proteus import Model
from trytond.modules.company.tests.tools import create_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class TestMultipleCeiling(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        config = activate_modules('production_semielaborate', create_company)
        Uom = Model.get('product.uom')
        Template = Model.get('product.template')
        Bom = Model.get('production.bom')
        Production = Model.get('production')
        Location = Model.get('stock.location')
        unit, = Uom.find([('name', '=', 'Kilogram')])
        warehouse, = Location.find([('code', '=', 'WH')])
        template = Template(name='Bread', type='goods', default_uom=unit,
            producible=True)
        template.save()
        product, = template.products
        semi_template = Template(name='Dough', type='goods', default_uom=unit)
        semi_template.save()
        semi, = semi_template.products
        semi.is_semielaborate = True
        semi.save()
        bom = Bom(name='Bread from dough')
        input_ = bom.inputs.new(product=semi, quantity=1)
        input_.unit = unit
        output = bom.outputs.new(product=product, quantity=100)
        output.unit = unit
        bom.save()
        production = Production(product=product, bom=bom, warehouse=warehouse)
        for quantity, expected in [(0, 0), (1, 1), (100, 1), (101, 2),
                (3720.9, 38), (3800, 38)]:
            production.quantity = quantity
            self.assertEqual(production.semielaborate_multiple, expected)
            self.assertEqual(production.quantity, quantity)
        production.semielaborate_multiple = 2.1
        self.assertEqual(production.semielaborate_multiple, 3)
        self.assertEqual(production.quantity, 300)
        production.save()
        # Imports and RPC calls must round up even without client on-changes.
        Production._proxy.write([production.id],
            {'semielaborate_multiple': 37.209}, config.context)
        production.reload()
        self.assertEqual(production.semielaborate_multiple, 38)
        self.assertEqual(production.quantity, 300)
        values = production._get_values()
        values.pop('id', None)
        values['semielaborate_multiple'] = 2.01
        ids = Production._proxy.create([values], config.context)
        self.assertEqual(Production(ids[0]).semielaborate_multiple, 3)
        # Decimal batch sizes must not add a batch due to float division noise.
        bom.outputs[0].quantity = 0.01
        bom.save()
        production.bom = Bom(bom.id)
        production.quantity = 0.07
        self.assertEqual(production.semielaborate_multiple, 7)
