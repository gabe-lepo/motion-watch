use serde::{Deserialize, Serialize};
use time::OffsetDateTime;
use uuid::Uuid;

#[derive(Serialize)]
pub struct Device {
    pub id: Uuid,
    pub name: String,
    pub location: Option<String>,
    pub last_seen: Option<OffsetDateTime>,
    pub created_at: OffsetDateTime,
}

#[derive(Deserialize)]
pub struct DeviceRegisterParams {
    pub name: String,
    pub location: Option<String>,
}

#[derive(Serialize)]
pub struct DeviceRegisterResponse {
    pub name: String,
    pub location: Option<String>,
}

#[derive(Deserialize)]
pub struct DeviceUpdateParams {
    pub name: Option<String>,
    pub location: Option<String>,
}
