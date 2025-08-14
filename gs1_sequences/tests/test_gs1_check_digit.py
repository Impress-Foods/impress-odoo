from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("standard", "impress")
class TestGS1CheckDigit(TransactionCase):
    def setUp(self):
        super().setUp()
        self.sequence_model = self.env["ir.sequence"]

    def test_gs1_check_digit_basic(self):
        """Test basic GS1 check digit calculation"""
        # Test case 1: Known GS1 example
        result = self.sequence_model._gs1_check_digit("0123456789012")
        self.assertEqual(result, "8")

        # Test case 2: Simple single digit
        # 3x1=3, 10-3=7
        result = self.sequence_model._gs1_check_digit("1")
        self.assertEqual(result, "7")

        # Test case 3: Two digits
        # 3x1+1x2=5, 10-5=5
        result = self.sequence_model._gs1_check_digit("12")
        self.assertEqual(result, "5")

    def test_gs1_check_digit_multiples_of_ten(self):
        """Test GS1 check digit when sum is multiple of 10"""
        # Test case where sum_of_digits % 10 == 0
        result = self.sequence_model._gs1_check_digit("0000000000000")
        self.assertEqual(result, "0")

        # Test case that results in sum being multiple of 10
        # Manual calculation: 3*5 + 5 = 20. 20-20 = 0
        result = self.sequence_model._gs1_check_digit("55")
        self.assertEqual(result, "0")

    def test_gs1_check_digit_edge_cases(self):
        """Test edge cases for GS1 check digit calculation"""
        # Test with all zeros
        result = self.sequence_model._gs1_check_digit("000")
        self.assertEqual(result, "0")

        # Test with all nines
        # 3x9 + 1x9 + 3x9 = 27 + 9 + 27 = 63, 70-63=7
        result = self.sequence_model._gs1_check_digit("999")
        self.assertEqual(result, "7")

        # Test with single zero
        result = self.sequence_model._gs1_check_digit("0")
        self.assertEqual(result, "0")

    def test_gs1_check_digit_algorithm_verification(self):
        """Test algorithm with known GS1 examples"""
        # UPC-A example: 03600029145
        result = self.sequence_model._gs1_check_digit("03600029145")
        self.assertEqual(result, "2")

        # EAN-13 example: 590123412345
        result = self.sequence_model._gs1_check_digit("590123412345")
        self.assertEqual(result, "7")

    def test_gs1_check_digit_error_handling(self):
        """Test error handling for invalid inputs"""
        # Test with non-numeric string (should raise ValidationError)
        with self.assertRaises(ValidationError):  # type: ignore
            self.sequence_model._gs1_check_digit("abc")

        # Test with empty string
        with self.assertRaises(ValidationError):  # type: ignore
            self.sequence_model._gs1_check_digit("")

        # Test with mixed alphanumeric
        with self.assertRaises(ValidationError):  # type: ignore
            self.sequence_model._gs1_check_digit("12a34")

    def test_gs1_check_digit_long_sequences(self):
        """Test with longer sequences"""
        # Test 20-digit sequence
        result = self.sequence_model._gs1_check_digit("12345678901234567890")
        # Manual calculation: odds=[1,3,5,7,9,1,3,5,7,9], evens=[2,4,6,8,0,2,4,6,8,0]
        # 3*(1+3+5+7+9+1+3+5+7+9) + (2+4+6+8+0+2+4+6+8+0) = 3*50 + 40 = 190
        # nearest_ten = 200, check_digit = 200 - 190 = 10 -> "0"
        self.assertEqual(result, "0")
