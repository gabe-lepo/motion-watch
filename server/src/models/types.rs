use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Serialize)]
pub struct Device {
    pub id: Uuid,
    pub hw_identifier: String,
    pub name: String,
    pub location: Option<String>,
    pub last_seen: i64,
    pub created_at: i64,
}

#[derive(Deserialize)]
pub struct DeviceRegisterParams {
    pub hw_identifier: String,
    pub name: String,
    pub location: Option<String>,
}
