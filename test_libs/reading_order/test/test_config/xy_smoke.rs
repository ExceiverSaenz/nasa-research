//! Configuration-only client for the pinned third-party XY-Cut++ implementation.
use xycut_plus_plus::{BoundingBox, XYCutConfig, XYCutPlusPlus};
use xycut_plus_plus::traits::SemanticLabel;

#[derive(Clone)]
struct Element { id: usize, y: f32 }
impl BoundingBox for Element {
    fn id(&self) -> usize { self.id }
    fn center(&self) -> (f32, f32) { (55.0, self.y + 5.0) }
    fn bounds(&self) -> (f32, f32, f32, f32) { (10.0, self.y, 100.0, self.y + 10.0) }
    fn iou(&self, other: &Self) -> f32 {
        let height = (self.y + 10.0).min(other.y + 10.0) - self.y.max(other.y);
        let intersection = 90.0 * height.max(0.0);
        intersection / (1800.0 - intersection)
    }
    fn should_mask(&self) -> bool { false }
    fn semantic_label(&self) -> SemanticLabel { SemanticLabel::Regular }
}
fn main() {
    let elements = [Element { id: 0, y: 60.0 }, Element { id: 1, y: 10.0 }];
    let result = XYCutPlusPlus::new(XYCutConfig::default())
        .compute_order(&elements, 0.0, 0.0, 600.0, 800.0);
    println!("{:?}", result);
}
