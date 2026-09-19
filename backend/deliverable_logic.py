"""
Production-ready pricing calculator package.
Implements a flexible pricing calculator with support for multiple pricing models,
discounts, taxes, and comprehensive input validation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union, Any, Callable
from enum import Enum
import json
import math
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing_extensions import Literal


class PricingModel(str, Enum):
    """Supported pricing models."""
    FLAT_RATE = "flat_rate"
    PER_UNIT = "per_unit"
    TIERED = "tiered"
    VOLUME = "volume"
    SUBSCRIPTION = "subscription"


class DiscountType(str, Enum):
    """Supported discount types."""
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"
    BULK = "bulk"
    PROMOTIONAL = "promotional"


class TaxType(str, Enum):
    """Supported tax types."""
    SALES_TAX = "sales_tax"
    VAT = "vat"
    GST = "gst"
    CUSTOM = "custom"


@dataclass
class PriceComponent:
    """Represents a single price component."""
    name: str
    amount: Decimal
    quantity: int = 1
    unit: str = "item"
    
    def total(self) -> Decimal:
        """Calculate total for this component."""
        return self.amount * Decimal(self.quantity)


@dataclass
class Discount:
    """Represents a discount."""
    discount_type: DiscountType
    value: Decimal
    name: str = ""
    max_amount: Optional[Decimal] = None
    min_purchase: Optional[Decimal] = None
    
    def apply(self, amount: Decimal) -> Decimal:
        """Apply discount to amount."""
        if self.discount_type == DiscountType.PERCENTAGE:
            discount_amount = amount * (self.value / Decimal(100))
        elif self.discount_type == DiscountType.FIXED_AMOUNT:
            discount_amount = self.value
        else:
            discount_amount = Decimal(0)
        
        if self.max_amount and discount_amount > self.max_amount:
            discount_amount = self.max_amount
        
        return max(discount_amount, Decimal(0))


@dataclass
class Tax:
    """Represents a tax."""
    tax_type: TaxType
    rate: Decimal
    name: str = ""
    inclusive: bool = False
    
    def calculate(self, amount: Decimal) -> Decimal:
        """Calculate tax amount."""
        return amount * (self.rate / Decimal(100))


class PricingCalculator:
    """Main pricing calculator class."""
    
    def __init__(self, pricing_model: PricingModel = PricingModel.PER_UNIT):
        self.pricing_model = pricing_model
        self.components: List[PriceComponent] = []
        self.discounts: List[Discount] = []
        self.taxes: List[Tax] = []
        self.currency: str = "USD"
        self.rounding_precision: int = 2
        
    def add_component(self, name: str, amount: Union[Decimal, float, int], 
                     quantity: int = 1, unit: str = "item") -> None:
        """Add a price component."""
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if amount < 0:
            raise ValueError("Amount must be non-negative")
        
        decimal_amount = Decimal(str(amount))
        self.components.append(PriceComponent(
            name=name,
            amount=decimal_amount,
            quantity=quantity,
            unit=unit
        ))
    
    def add_discount(self, discount_type: DiscountType, value: Union[Decimal, float, int],
                    name: str = "", max_amount: Optional[Union[Decimal, float, int]] = None,
                    min_purchase: Optional[Union[Decimal, float, int]] = None) -> None:
        """Add a discount."""
        decimal_value = Decimal(str(value))
        if decimal_value < 0:
            raise ValueError("Discount value must be non-negative")
        
        decimal_max = Decimal(str(max_amount)) if max_amount is not None else None
        decimal_min = Decimal(str(min_purchase)) if min_purchase is not None else None
        
        self.discounts.append(Discount(
            discount_type=discount_type,
            value=decimal_value,
            name=name,
            max_amount=decimal_max,
            min_purchase=decimal_min
        ))
    
    def add_tax(self, tax_type: TaxType, rate: Union[Decimal, float, int],
               name: str = "", inclusive: bool = False) -> None:
        """Add a tax."""
        decimal_rate = Decimal(str(rate))
        if decimal_rate < 0:
            raise ValueError("Tax rate must be non-negative")
        
        self.taxes.append(Tax(
            tax_type=tax_type,
            rate=decimal_rate,
            name=name,
            inclusive=inclusive
        ))
    
    def calculate_subtotal(self) -> Decimal:
        """Calculate subtotal from all components."""
        if not self.components:
            return Decimal(0)
        
        subtotal = Decimal(0)
        for component in self.components:
            subtotal += component.total()
        
        return subtotal.quantize(
            Decimal('0.01'), 
            rounding=ROUND_HALF_UP
        )
    
    def calculate_discounts(self, subtotal: Decimal) -> Tuple[Decimal, List[Dict[str, Any]]]:
        """Calculate total discounts and return breakdown."""
        if not self.discounts:
            return Decimal(0), []
        
        total_discount = Decimal(0)
        discount_breakdown = []
        
        for discount in self.discounts:
            if discount.min_purchase and subtotal < discount.min_purchase:
                continue
            
            discount_amount = discount.apply(subtotal)
            total_discount += discount_amount
            
            discount_breakdown.append({
                "name": discount.name,
                "type": discount.discount_type.value,
                "amount": float(discount_amount),
                "value": float(discount.value)
            })
        
        # Cap discount at subtotal
        if total_discount > subtotal:
            total_discount = subtotal
        
        return total_discount.quantize(
            Decimal('0.01'), 
            rounding=ROUND_HALF_UP
        ), discount_breakdown
    
    def calculate_taxes(self, taxable_amount: Decimal) -> Tuple[Decimal, List[Dict[str, Any]]]:
        """Calculate total taxes and return breakdown."""
        if not self.taxes:
            return Decimal(0), []
        
        total_tax = Decimal(0)
        tax_breakdown = []
        
        for tax in self.taxes:
            if tax.inclusive:
                # For inclusive taxes, calculate tax from gross amount
                tax_amount = taxable_amount - (taxable_amount / (Decimal(1) + (tax.rate / Decimal(100))))
            else:
                tax_amount = tax.calculate(taxable_amount)
            
            total_tax += tax_amount
            
            tax_breakdown.append({
                "name": tax.name,
                "type": tax.tax_type.value,
                "rate": float(tax.rate),
                "amount": float(tax_amount),
                "inclusive": tax.inclusive
            })
        
        return total_tax.quantize(
            Decimal('0.01'), 
            rounding=ROUND_HALF_UP
        ), tax_breakdown
    
    def calculate_total(self) -> Dict[str, Any]:
        """
        Calculate total price with all components, discounts, and taxes.
        Returns a detailed breakdown.
        """
        # Calculate subtotal
        subtotal = self.calculate_subtotal()
        
        # Calculate discounts
        total_discount, discount_breakdown = self.calculate_discounts(subtotal)
        
        # Calculate amount after discounts
        amount_after_discounts = subtotal - total_discount
        if amount_after_discounts < 0:
            amount_after_discounts = Decimal(0)
        
        # Separate inclusive and exclusive taxes
        exclusive_taxes = [tax for tax in self.taxes if not tax.inclusive]
        inclusive_taxes = [tax for tax in self.taxes if tax.inclusive]
        
        # Calculate exclusive taxes
        exclusive_tax_amount = Decimal(0)
        exclusive_tax_breakdown = []
        
        for tax in exclusive_taxes:
            tax_amount = tax.calculate(amount_after_discounts)
            exclusive_tax_amount += tax_amount
            exclusive_tax_breakdown.append({
                "name": tax.name,
                "type": tax.tax_type.value,
                "rate": float(tax.rate),
                "amount": float(tax_amount),
                "inclusive": False
            })
        
        # Calculate inclusive taxes
        inclusive_tax_amount = Decimal(0)
        inclusive_tax_breakdown = []
        
        for tax in inclusive_taxes:
            # For inclusive taxes, the tax is already included in amount_after_discounts
            # We need to calculate what portion of amount_after_discounts is tax
            tax_amount = amount_after_discounts - (amount_after_discounts / (Decimal(1) + (tax.rate / Decimal(100))))
            inclusive_tax_amount += tax_amount
            inclusive_tax_breakdown.append({
                "name": tax.name,
                "type": tax.tax_type.value,
                "rate": float(tax.rate),
                "amount": float(tax_amount),
                "inclusive": True
            })
        
        total_tax = exclusive_tax_amount + inclusive_tax_amount
        all_tax_breakdown = exclusive_tax_breakdown + inclusive_tax_breakdown
        
        # Calculate final total
        if inclusive_taxes:
            # With inclusive taxes, the total is amount_after_discounts
            total = amount_after_discounts
        else:
            # With only exclusive taxes, add tax to amount_after_discounts
            total = amount_after_discounts + exclusive_tax_amount
        
        # Round all amounts
        subtotal = subtotal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_discount = total_discount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        amount_after_discounts = amount_after_discounts.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_tax = total_tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        return {
            "subtotal": float(subtotal),
            "discounts": discount_breakdown,
            "total_discount": float(total_discount),
            "amount_after_discounts": float(amount_after_discounts),
            "taxes": all_tax_breakdown,
            "total_tax": float(total_tax),
            "total": float(total),
            "currency": self.currency,
            "components": [
                {
                    "name": c.name,
                    "unit_price": float(c.amount),
                    "quantity": c.quantity,
                    "unit": c.unit,
                    "total": float(c.total())
                }
                for c in self.components
            ]
        }
    
    def clear(self) -> None:
        """Clear all components, discounts, and taxes."""
        self.components.clear()
        self.discounts.clear()
        self.taxes.clear()
    
    def to_json(self) -> str:
        """Serialize calculator state to JSON."""
        state = {
            "pricing_model": self.pricing_model.value,
            "currency": self.currency,
            "rounding_precision": self.rounding_precision,
            "components": [
                {
                    "name": c.name,
                    "amount": float(c.amount),
                    "quantity": c.quantity,
                    "unit": c.unit
                }
                for c in self.components
            ],
            "discounts": [
                {
                    "discount_type": d.discount_type.value,
                    "value": float(d.value),
                    "name": d.name,
                    "max_amount": float(d.max_amount) if d.max_amount else None,
                    "min_purchase": float(d.min_purchase) if d.min_purchase else None
                }
                for d in self.discounts
            ],
            "taxes": [
                {
                    "tax_type": t.tax_type.value,
                    "rate": float(t.rate),
                    "name": t.name,
                    "inclusive": t.inclusive
                }
                for t in self.taxes
            ]
        }
        return json.dumps(state, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PricingCalculator':
        """Create calculator from JSON string."""
        state = json.loads(json_str)
        calculator = cls(PricingModel(state["pricing_model"]))
        calculator.currency = state["currency"]
        calculator.rounding_precision = state["rounding_precision"]
        
        for comp in state["components"]:
            calculator.add_component(
                name=comp["name"],
                amount=Decimal(str(comp["amount"])),
                quantity=comp["quantity"],
                unit=comp["unit"]
            )
        
        for disc in state["discounts"]:
            calculator.add_discount(
                discount_type=DiscountType(disc["discount_type"]),
                value=Decimal(str(disc["value"])),
                name=disc["name"],
                max_amount=Decimal(str(disc["max_amount"])) if disc["max_amount"] else None,
                min_purchase=Decimal(str(disc["min_purchase"])) if disc["min_purchase"] else None
            )
        
        for tax in state["taxes"]:
            calculator.add_tax(
                tax_type=TaxType(tax["tax_type"]),
                rate=Decimal(str(tax["rate"])),
                name=tax["name"],
                inclusive=tax["inclusive"]
            )
        
        return calculator


# Utility functions for common pricing scenarios

def calculate_simple_price(unit_price: float, quantity: int, 
                          discount_percent: float = 0.0, 
                          tax_rate: float = 0.0) -> Dict[str, float]:
    """
    Calculate simple price with unit price, quantity, discount, and tax.
    
    Args:
        unit_price: Price per unit
        quantity: Number of units
        discount_percent: Discount percentage (0-100)
        tax_rate: Tax rate percentage (0-100)
    
    Returns:
        Dictionary with price breakdown
    """
    calculator = PricingCalculator()
    calculator.add_component("Item", unit_price, quantity)
    
    if discount_percent > 0:
        calculator.add_discount(
            discount_type=DiscountType.PERCENTAGE,
            value=Decimal(str(discount_percent)),
            name="Standard Discount"
        )
    
    if tax_rate > 0:
        calculator.add_tax(
            tax_type=TaxType.SALES_TAX,
            rate=Decimal(str(tax_rate)),
            name="Sales Tax"
        )
    
    return calculator.calculate_total()


def validate_pricing_input(unit_price: float, quantity: int, 
                          discount_percent: float) -> Tuple[bool, List[str]]:
    """
    Validate pricing input parameters.
    
    Args:
        unit_price: Price per unit
        quantity: Number of units
        discount_percent: Discount percentage
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    if unit_price < 0:
        errors.append("Unit price must be non-negative")
    
    if quantity <= 0:
        errors.append("Quantity must be positive")
    
    if discount_percent < 0 or discount_percent > 100:
        errors.append("Discount percentage must be between 0 and 100")
    
    return len(errors) == 0, errors


def calculate_tiered_price(tiers: List[Tuple[int, float]], 
                          quantity: int) -> Dict[str, Any]:
    """
    Calculate price using tiered pricing model.
    
    Args:
        tiers: List of (max_quantity, price) tuples
        quantity: Total quantity
    
    Returns:
        Dictionary with tiered price breakdown
    """
    if not tiers:
        raise ValueError("Tiers list cannot be empty")
    
    # Sort tiers by max_quantity
    sorted_tiers = sorted(tiers, key=lambda x: x[0])
    
    total_price = Decimal(0)
    remaining_quantity = quantity
    tier_breakdown = []
    
    for i, (max_qty, price) in enumerate(sorted_tiers):
        if i == len(sorted_tiers) - 1:
            # Last tier: use all remaining quantity
            tier_qty = remaining_quantity
        else:
            next_max = sorted_tiers[i + 1][0]
            tier_qty = min(remaining_quantity, max_qty)
        
        if tier_qty > 0:
            tier_price = Decimal(str(price)) * Decimal(tier_qty)
            total_price += tier_price
            tier_breakdown.append({
                "tier": i + 1,
                "max_quantity": max_qty,
                "unit_price": price,
                "quantity": tier_qty,
                "tier_total": float(tier_price)
            })
            remaining_quantity -= tier_qty
        
        if remaining_quantity <= 0:
            break
    
    return {
        "total_price": float(total_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        "tier_breakdown": tier_breakdown,
        "quantity": quantity
    }