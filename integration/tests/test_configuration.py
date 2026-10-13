import importlib
import math
import unittest

class ConfigurationContract(unittest.TestCase):
    def setUp(self):
        self.native = importlib.import_module("hyprn_mvp_integration.native")
        self.port = {"id": 17, "name": "x", "units": "km", "shape": "1", "type": "Float"}

    def validate(self, value, units="km"):
        return self.native.validate_configuration([self.port], [{"port_id": 17, "value": value, "units": units, "provenance": "Entered by engineer"}])

    def test_missing_is_not_zero(self):
        with self.assertRaises(ValueError):
            self.native.validate_configuration([self.port], [])
        for value in (None, "", " "):
            with self.assertRaises(ValueError): self.validate(value)
        self.assertEqual(self.validate(0)[0]["value"], 0)

    def test_adjacent_negative_and_zero(self):
        for value in (0, -0.0, -2, 1, math.nextafter(1, 2)):
            self.assertEqual(self.validate(value)[0]["value"], value)

    def test_nonfinite_bool_and_arrays_rejected(self):
        for value in (float('nan'), float('inf'), -float('inf'), [1], True, {}, "NaN"):
            with self.assertRaises(ValueError): self.validate(value)

    def test_native_multiplicative_conversion(self):
        self.assertEqual(self.validate(2000, "m")[0]["value"], 2)

    def test_incompatible_and_affine_units(self):
        with self.assertRaises(ValueError): self.validate(2, "s")
        self.port['units'] = 'K'
        with self.assertRaises(ValueError): self.validate(20, "degC")

    def test_identity_binding_order_and_duplicate(self):
        other = dict(self.port, id=18, name='z')
        rows = [{"port_id": i, "value": i, "units": "km", "provenance": "Explicit"} for i in (17,18)]
        self.assertEqual(self.native.validate_configuration([self.port, other], rows), self.native.validate_configuration([other,self.port], rows[::-1]))
        with self.assertRaises(ValueError): self.native.validate_configuration([self.port], rows)
        with self.assertRaises(ValueError): self.native.validate_configuration([self.port], [rows[0],rows[0]])

    def test_scalar_and_no_free_inputs(self):
        self.assertEqual(self.native.validate_configuration([], []), [])
        self.port['shape']='(2,)'
        with self.assertRaises(ValueError): self.validate(1)

    def test_changed_contract_requires_explicit_review(self):
        row=self.validate(2)[0]
        self.port['units']='m'
        with self.assertRaisesRegex(ValueError,'changed'):
            self.native.validate_configuration([self.port],[row])
        row.pop('contract')
        self.assertEqual(self.native.validate_configuration([self.port],[row])[0]['value'],2000)

    def test_units_are_bounded_declared_data(self):
        for expression in ("__import__('os').system('touch /tmp/unit-exec')", 'm**(99**99)', 'm**99', 'm[0]'):
            with self.assertRaises(ValueError): self.validate(1,expression)

    def test_criteria_units_and_allowlist(self):
        output=dict(self.port,id=19)
        criterion={'port_id':19,'operator':'<=','threshold':2000,'units':'m'}
        self.assertEqual(self.native.validate_criteria([output],[criterion])[0]['threshold'],2)
        for bad in (dict(criterion,operator='eval'),dict(criterion,port_id=20),dict(criterion,threshold=float('nan'))):
            with self.assertRaises(ValueError): self.native.validate_criteria([output],[bad])

    def test_static_source_port_error_and_no_execution(self):
        self.native.validate_source("raise RuntimeError('must never execute')\noutputs['u'] = inputs['x']\n", ['x'], ['u'])
        for source in ("if :", "outputs['wrong'] = inputs['x']", "outputs['u'] = inputs['missing']"):
            with self.assertRaises(ValueError): self.native.validate_source(source, ['x'], ['u'])

if __name__ == '__main__': unittest.main()
