/**
 * Pharmacy Discovery with Geolocation and Real Maps Navigation
 */

document.addEventListener("DOMContentLoaded", () => {
  const locateBtn = document.getElementById("use-location-btn");
  const searchForm = document.getElementById("pharmacy-search-form");
  const resultsContainer = document.getElementById("pharmacy-results-list");
  const searchStatus = document.getElementById("pharmacy-search-status");

  if (locateBtn) {
    locateBtn.addEventListener("click", () => {
      if (!("geolocation" in navigator)) {
        showToast("Geolocation is not supported by your browser.", "danger");
        return;
      }
      searchStatus.innerHTML = "<p>Detecting your current location...</p>";
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const lat = pos.coords.latitude;
          const lng = pos.coords.longitude;
          fetchPharmacies({ lat, lng });
        },
        async (err) => {
          console.warn("Browser GPS unavailable, trying IP-based location fallback:", err);
          searchStatus.innerHTML = "<p>Detecting approximate location via network IP...</p>";
          try {
            const ipRes = await fetch("https://ipwho.is/");
            const ipData = await ipRes.json();
            if (ipData && ipData.latitude && ipData.longitude) {
              fetchPharmacies({
                lat: ipData.latitude,
                lng: ipData.longitude,
                address: `${ipData.city || ''}, ${ipData.region || ''}`
              });
              return;
            }
          } catch (ipErr) {
            console.warn("IP geolocation fallback also failed:", ipErr);
          }
          searchStatus.innerHTML = "<p class='alert alert-warning'>GPS access was denied or unavailable. Please type your city or area in the search box above (e.g. 'Delhi', 'Mumbai', 'Indiranagar') and click Search.</p>";
        },
        { timeout: 7000, enableHighAccuracy: true }
      );
    });
  }

  if (searchForm) {
    searchForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const address = document.getElementById("manual-address-input").value;
      const radius = document.getElementById("radius-select").value;
      const openNow = document.getElementById("open-now-checkbox")?.checked;
      if (!address.trim()) {
        showToast("Please enter an address or click 'Use Current Location'.", "warning");
        return;
      }
      fetchPharmacies({ address, radius, open_now: openNow });
    });
  }

  // Quick city button handlers
  document.querySelectorAll(".quick-city-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const city = btn.getAttribute("data-city");
      const addrInput = document.getElementById("manual-address-input");
      if (addrInput) addrInput.value = city;
      const radius = document.getElementById("radius-select")?.value || 5000;
      fetchPharmacies({ address: city, radius: radius });
    });
  });

  async function fetchPharmacies(params) {
    resultsContainer.innerHTML = "<div class='skeleton' style='height: 120px; margin-bottom: 1rem;'></div>";
    searchStatus.innerHTML = "<p>Searching verified pharmacy registries...</p>";

    const query = new URLSearchParams(params).toString();
    try {
      const res = await fetch(`/pharmacy/search?${query}`);
      const data = await res.json();

      if (!res.ok) {
        searchStatus.innerHTML = `<p class='alert alert-danger'>${data.message || 'Error searching pharmacies.'}</p>`;
        resultsContainer.innerHTML = "";
        return;
      }

      if (data.pharmacies.length === 0) {
        searchStatus.innerHTML = "<p class='alert alert-info'>No pharmacies found within the specified radius. Try expanding the search radius.</p>";
        resultsContainer.innerHTML = "";
        return;
      }

      searchStatus.innerHTML = `<p>Found <strong>${data.count}</strong> nearby pharmacies near <em>${data.location.name}</em>:</p>`;
      
      let html = "";
      data.pharmacies.forEach((p) => {
        html += `
          <div class="card" style="margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 0.5rem;">
              <div>
                <h3 style="font-size: 1.15rem; font-weight: 700;">${p.name}</h3>
                <p style="color: var(--text-muted); font-size: 0.88rem; margin: 0.2rem 0;">📍 ${p.address}</p>
                ${p.phone ? `<p style="font-size: 0.85rem;">📞 <a href="tel:${p.phone}">${p.phone}</a></p>` : ''}
              </div>
              <div style="text-align: right;">
                <span class="badge" style="background: var(--secondary-light); color: var(--secondary); font-size: 0.85rem;">
                  🚗 ${p.distance_km} km away
                </span>
                <div style="margin-top: 0.5rem;">
                  <a href="${p.directions_url}" target="_blank" rel="noopener noreferrer" class="btn btn-outline-primary btn-sm">
                    Get Directions ↗
                  </a>
                </div>
              </div>
            </div>
            <div style="margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px solid var(--border-color); font-size: 0.78rem; color: var(--text-muted);">
              Data Source: ${p.source} • In-store inventory must be confirmed directly with pharmacy.
            </div>
          </div>
        `;
      });
      resultsContainer.innerHTML = html;

    } catch (err) {
      console.error("Pharmacy fetch error:", err);
      searchStatus.innerHTML = "<p class='alert alert-danger'>Network error while contacting pharmacy service.</p>";
      resultsContainer.innerHTML = "";
    }
  }
});
