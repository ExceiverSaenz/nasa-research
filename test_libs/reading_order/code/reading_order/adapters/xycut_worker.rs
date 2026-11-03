//! Nonpersistent stdin client for the pinned third-party XY-Cut++ candidate.
use std::io::{self,Read};
use xycut_plus_plus::{BoundingBox,XYCutConfig,XYCutPlusPlus};
use xycut_plus_plus::traits::SemanticLabel;
#[derive(Clone)]
struct Element { id:usize, b:(f32,f32,f32,f32), label:u8 }
impl BoundingBox for Element {
 fn id(&self)->usize { self.id }
 fn center(&self)->(f32,f32) { ((self.b.0+self.b.2)*0.5,(self.b.1+self.b.3)*0.5) }
 fn bounds(&self)->(f32,f32,f32,f32) { self.b }
 fn iou(&self,other:&Self)->f32 {
  let w=(self.b.2.min(other.b.2)-self.b.0.max(other.b.0)).max(0.0);
  let h=(self.b.3.min(other.b.3)-self.b.1.max(other.b.1)).max(0.0);
  let a=(self.b.2-self.b.0)*(self.b.3-self.b.1);
  let b=(other.b.2-other.b.0)*(other.b.3-other.b.1);
  if a+b-w*h>0.0 { w*h/(a+b-w*h) } else {0.0}
 }
 fn should_mask(&self)->bool { self.label!=0 }
 fn semantic_label(&self)->SemanticLabel {
  match self.label {1=>SemanticLabel::HorizontalTitle,2=>SemanticLabel::Vision,_=>SemanticLabel::Regular}
 }
}
fn main() {
 let mut s=String::new();io::stdin().read_to_string(&mut s).unwrap();
 let mut lines=s.lines();let dims:Vec<f32>=lines.next().unwrap().split_whitespace().map(|x|x.parse().unwrap()).collect();
 assert_eq!(dims.len(),2);
 let elements:Vec<Element>=lines.map(|line|{
  let v:Vec<&str>=line.split_whitespace().collect();assert_eq!(v.len(),6);
  Element{id:v[0].parse().unwrap(),b:(v[1].parse().unwrap(),v[2].parse().unwrap(),v[3].parse().unwrap(),v[4].parse().unwrap()),label:v[5].parse().unwrap()}
 }).collect();
 let order=XYCutPlusPlus::new(XYCutConfig::default()).compute_order(&elements,0.0,0.0,dims[0],dims[1]);
 println!("{:?}",order);
}
