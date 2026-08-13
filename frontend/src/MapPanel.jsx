import { CircleMarker, MapContainer, Polygon, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import { useEffect } from 'react'

function Recenter({ center }) {
  const map = useMap()
  useEffect(() => { map.setView(center, map.getZoom()) }, [center, map])
  return null
}

const polygonPositions = (geometry) =>
  geometry?.coordinates?.[0]?.map(([lon, lat]) => [lat, lon]) || []

export default function MapPanel({ bootstrap, response, context }) {
  const center = response?.map_state?.center || [context.lat, context.lon]
  const evac = response?.map_state?.evacuation
  const incidents = response?.map_state?.incidents || []
  const shelters = response?.map_state?.shelters || bootstrap?.map?.shelters || []
  const selected = response?.map_state?.selected_shelter
  const zones = evac?.geometry ? [{ ...evac, geometry: evac.geometry }] : []

  return (
    <div className="map-shell">
      <MapContainer center={center} zoom={11} scrollWheelZoom className="map">
        <Recenter center={center} />
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {zones.map((zone, index) => (
          <Polygon
            key={`zone-${index}`}
            positions={polygonPositions(zone.geometry)}
            pathOptions={{ color: '#ff614d', weight: 2, fillColor: '#ff614d', fillOpacity: 0.18 }}
          >
            <Popup>{zone.zone_name} · Level {zone.level}</Popup>
          </Polygon>
        ))}
        {incidents.map((incident) => (
          <Polygon
            key={incident.event_id}
            positions={polygonPositions(incident.geometry)}
            pathOptions={{ color: '#ef402f', weight: 1.5, fillColor: '#ef402f', fillOpacity: 0.28 }}
          >
            <Popup><strong>{incident.name}</strong><br />{incident.acres.toLocaleString()} acres</Popup>
          </Polygon>
        ))}
        <CircleMarker center={[context.lat, context.lon]} radius={7} pathOptions={{ color: '#fff', fillColor: '#26d9c7', fillOpacity: 1 }}>
          <Popup>Your demo location</Popup>
        </CircleMarker>
        {shelters.map((shelter) => (
          <CircleMarker
            key={shelter.shelter_id}
            center={[shelter.lat, shelter.lon]}
            radius={selected?.shelter_id === shelter.shelter_id ? 9 : 6}
            pathOptions={{ color: '#081315', weight: 2, fillColor: '#f8c65d', fillOpacity: 1 }}
          >
            <Popup><strong>{shelter.name}</strong><br />{shelter.address}</Popup>
          </CircleMarker>
        ))}
        {selected?.route && (
          <Polyline
            positions={selected.route.map(([lon, lat]) => [lat, lon])}
            pathOptions={{ color: '#26d9c7', weight: 4, dashArray: '8 7' }}
          />
        )}
      </MapContainer>
      <div className="map-key">
        <span><i className="dot user-dot" />You</span>
        <span><i className="dot fire-dot" />Fire / evacuation</span>
        <span><i className="dot shelter-dot" />Shelter</span>
      </div>
      <div className="replay-pill">REPLAY · NOT LIVE</div>
    </div>
  )
}

