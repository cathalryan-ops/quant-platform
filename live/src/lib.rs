//! Live execution engine (P8). Real orders, hard guardrails in the order
//! path, and a startup that refuses unless every safety condition holds.

pub mod broker;
pub mod session;
pub mod startup;
