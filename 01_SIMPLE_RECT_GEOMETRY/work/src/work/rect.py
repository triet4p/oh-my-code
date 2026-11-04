from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Rect:
    x1: float
    y1: float
    x2: float
    y2: float

    def _check_finite_value(self, value) -> None:
        if not isinstance(value, (int, float)):
            raise ValueError(f"Value must be a number, got {type(value).__name__}")
        if value is None or not (float('-inf') < value < float('inf')):
            raise ValueError(f"Value must be a finite number, got {value}")

    def __post_init__(self):
        self._check_finite_value(self.x1)
        self._check_finite_value(self.y1)
        self._check_finite_value(self.x2)
        self._check_finite_value(self.y2)

        if (self.x2 <= self.x1) or self.y2 <= self.y1:
            raise ValueError("Invalid rectangle coordinates: x2 must be greater than x1 and y2 must be greater than y1.")

    def area(self) -> float:
        """Calculate the area of the rectangle."""
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    def intersection_area(self, other: 'Rect') -> float:
        """Calculate the area of intersection with another rectangle."""
        intersection_x = (
            max(self.x1, other.x1), min(self.x2, other.x2)
        )
        intersection_y = (
            max(self.y1, other.y1), min(self.y2, other.y2)
        )

        if intersection_x[0] < intersection_x[1] and intersection_y[0] < intersection_y[1]:
            return (intersection_x[1] - intersection_x[0]) * (intersection_y[1] - intersection_y[0])
        return 0.0

    def intersects(self, other: 'Rect') -> bool:
        """Check if this rectangle intersects with another rectangle."""
        return self.intersection_area(other) > 0.0

    def coverage_of(self, other: 'Rect') -> float:
        """Calculate the coverage of this rectangle over another rectangle."""
        intersection_area = self.intersection_area(other)
        if intersection_area == 0.0:
            return 0.0
        return intersection_area / other.area()

    def contains(self, other: 'Rect', *, tolerance: float = 0.0) -> bool:
        """Check if this rectangle completely contains another rectangle, with an optional tolerance."""
        if tolerance < 0 or self._check_finite_value(tolerance):
            raise ValueError("Tolerance must be a non-negative finite number.")
        if (self.x1 - tolerance <= other.x1 and
            self.y1 - tolerance <= other.y1 and
            self.x2 + tolerance >= other.x2 and
            self.y2 + tolerance >= other.y2
        ):
            return True 
        return False

    def is_inside(self, other: 'Rect', *, tolerance: float = 0.0) -> bool:
        """Check if this rectangle is completely inside another rectangle, with an optional tolerance."""
        if tolerance < 0 or self._check_finite_value(tolerance):
            raise ValueError("Tolerance must be a non-negative finite number.")
        if (self.x1 + tolerance >= other.x1 and
            self.y1 + tolerance >= other.y1 and
            self.x2 - tolerance <= other.x2 and
            self.y2 - tolerance <= other.y2
        ):
            return True 
        return False

    def contains_by_area(self, other: 'Rect', *, threshold: float = 0.7) -> bool:
        """Check if this rectangle contains another rectangle based on area coverage."""
        if threshold < 0 or threshold > 1:
            raise ValueError("Threshold must be between 0 and 1.")
        coverage = self.coverage_of(other)
        return coverage >= threshold

    def translate(self, dx: float, dy: float) -> 'Rect':
        """Translate the rectangle by dx and dy."""
        self._check_finite_value(dx)
        self._check_finite_value(dy)
        return Rect(self.x1 + dx, self.y1 + dy, self.x2 + dx, self.y2 + dy)


if __name__ == "__main__":
    A = Rect(0, 0, 10, 10)
    B = Rect(2, 2, 8, 8)
    C = Rect(8, 8, 12, 12)

    print(f"Area of A: {A.area()}")
    print(f"Area of B: {B.area()}")
    print(f"Area of C: {C.area()}")

    print(f"Intersection area of A and B: {A.intersection_area(B)}")

    print(f"Coverage of A over B: {A.coverage_of(B)}")
    print(f"Coverage of B over A: {B.coverage_of(A)}")

    print(f"A contains B: {A.contains(B)}")
    print(f"B contains A: {B.contains(A)}")

    print(f"A contains B by area (threshold 0.7): {A.contains_by_area(B, threshold=0.7)}")
    print(f"B contains A by area (threshold 0.7): {B.contains_by_area(A, threshold=0.7)}")

    print(f"A intersection area with C: {A.intersection_area(C)}")
    print(f"A intersects C: {A.intersects(C)}")
    print(f"A contains C: {A.contains(C)}")

    print(f"A translated by (5, -2): {A.translate(5, -2)}")