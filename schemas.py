"""
Database Schemas for Bike Taxi App

Each Pydantic model represents a collection in your MongoDB database.
Collection name is the lowercase class name.

Examples:
- User -> "user"
- Ride -> "ride"
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal

class User(BaseModel):
    """
    Users of the platform: can be riders or drivers
    Collection name: "user"
    """
    name: str = Field(..., description="Full name")
    role: Literal["rider", "driver"] = Field(..., description="Role in the app")
    phone: Optional[str] = Field(None, description="Contact number")
    is_active: bool = Field(True, description="Whether user is active")

class DriverStatus(BaseModel):
    """
    Driver availability and last known location
    Collection name: "driverstatus"
    """
    user_id: str = Field(..., description="User id for the driver")
    is_available: bool = Field(True, description="Whether driver is available for rides")
    lat: Optional[float] = Field(None, description="Latitude")
    lng: Optional[float] = Field(None, description="Longitude")

class Ride(BaseModel):
    """
    Ride requests and lifecycle
    Collection name: "ride"
    """
    rider_id: str = Field(..., description="User id of the rider")
    pickup: str = Field(..., description="Pickup address or description")
    dropoff: str = Field(..., description="Dropoff address or description")
    status: Literal["requested", "accepted", "picked_up", "completed", "cancelled"] = Field("requested", description="Ride status")
    driver_id: Optional[str] = Field(None, description="Assigned driver user id")
    fare_estimate: Optional[float] = Field(None, ge=0, description="Estimated fare in currency units")
