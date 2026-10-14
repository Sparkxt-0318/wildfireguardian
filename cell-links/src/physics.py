"""Physics of microwave propagation through vegetation-fire flames and plumes.

All functions are modeled estimates. Inputs that come from measurements are
documented in docs/PARAMETERS.md and configs/physics.json.

Conventions
- Time dependence exp(-i w t); a wave exp(i k n x) decays when Im(n) > 0.
- Heights z are metres above local ground (the DEM surface).
- dB values for loss are positive numbers (loss = -20 log10 |E/E0|).
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.special import fresnel

# Physical constants (CODATA 2018)
C0 = 299_792_458.0
E_CH = 1.602176634e-19
M_E = 9.1093837015e-31
EPS0 = 8.8541878128e-12
K_B = 1.380649e-23
H_PL = 6.62607015e-34
G = 9.81
NP_TO_DB = 20.0 / np.log(10.0)  # 8.686 dB per neper

E_ION_K = 4.3407 * E_CH         # potassium first ionization energy (NIST ASD)
E_AFF_O2 = 0.448 * E_CH         # O2 electron affinity (Ervin et al. 2003)


# ---------------------------------------------------------------------------
# 1. Cold collisional (Drude) plasma
# ---------------------------------------------------------------------------
def plasma_freq2(ne):
    """Square of the angular plasma frequency (rad^2 s^-2) for electron density ne (m^-3)."""
    return np.asarray(ne) * E_CH**2 / (EPS0 * M_E)


def drude_index(f_hz, ne, nu):
    """Complex refractive index of a cold collisional plasma.

    eps = 1 - wp^2 / (w (w + i nu)); returns n = sqrt(eps) with Im(n) >= 0.
    """
    w = 2 * np.pi * np.asarray(f_hz, dtype=float)
    eps = 1.0 - plasma_freq2(ne) / (w * (w + 1j * np.asarray(nu, dtype=float)))
    n = np.sqrt(eps.astype(complex))
    return np.where(n.imag < 0, -n, n)


def specific_attenuation_db_per_m(f_hz, ne, nu):
    """Power attenuation of a plane wave in dB/m (exact Drude, not the weak-plasma limit)."""
    k0 = 2 * np.pi * np.asarray(f_hz) / C0
    return NP_TO_DB * k0 * drude_index(f_hz, ne, nu).imag


def specific_attenuation_weak(f_hz, ne, nu):
    """Weak-plasma limit wp << w: alpha = (wp^2 / 2c) nu / (w^2 + nu^2) Np/m, in dB/m."""
    w = 2 * np.pi * np.asarray(f_hz)
    return NP_TO_DB * plasma_freq2(ne) / (2 * C0) * nu / (w**2 + nu**2)


def invert_ne_from_loss(loss_db, path_m, f_hz, nu):
    """Electron density that gives loss_db over path_m at f_hz for collision frequency nu (weak limit)."""
    w = 2 * np.pi * f_hz
    alpha_np = loss_db / NP_TO_DB / path_m
    wp2 = alpha_np * 2 * C0 * (w**2 + nu**2) / nu
    return wp2 * EPS0 * M_E / E_CH**2


# ---------------------------------------------------------------------------
# 2. Ionization and temperature in the flame and plume
# ---------------------------------------------------------------------------
def saha_S(T):
    """Saha function for K <-> K+ + e (m^-3). Statistical weights g0=2, g+=1, ge=2 cancel to 1."""
    T = np.asarray(T, dtype=float)
    return (2 * np.pi * M_E * K_B * T / H_PL**2) ** 1.5 * np.exp(-E_ION_K / (K_B * T))


def saha_ne(T, nK):
    """Equilibrium electron density from thermal ionization of potassium with total K density nK."""
    S = saha_S(T)
    return 0.5 * (-S + np.sqrt(S**2 + 4 * S * nK))


def calibrate_nK(ne_ref, T_ref):
    """Total potassium density that makes Saha equilibrium give ne_ref at T_ref."""
    S = saha_S(T_ref)
    return ne_ref**2 / S + ne_ref


def free_electron_fraction(T, x_o2=0.15, p_pa=101_325.0):
    """Fraction of negative charge carried by free electrons when attachment to O2 is in
    equilibrium with thermal detachment (Saha-type balance with the O2 electron affinity).
    Statistical weight ratio g(O2)*g(e)/g(O2-) ~ 3*2/4 = 1.5 (approximate)."""
    T = np.asarray(T, dtype=float)
    n_o2 = x_o2 * p_pa / (K_B * T)
    Sd = 1.5 * (2 * np.pi * M_E * K_B * T / H_PL**2) ** 1.5 * np.exp(-E_AFF_O2 / (K_B * T))
    return 1.0 / (1.0 + n_o2 / Sd)


def collision_freq(T, nu_ref, T_ref):
    """Electron-neutral collision frequency at constant pressure: nu ~ N v_th ~ T^-1/2."""
    return nu_ref * np.sqrt(T_ref / np.asarray(T, dtype=float))


def line_plume_dT(z, intensity_kw_m, T_amb=288.0, alpha_entr=0.16, conv_frac=0.75):
    """Mean centreline excess temperature (K) of a pure line plume above a fireline.

    Top-hat Morton-Taylor-Turner similarity for a planar plume in a calm, neutral
    atmosphere: w = (B / 2 alpha)^(1/3), g' = w^2 / z, with buoyancy flux per unit
    length B = g Q'_conv / (rho cp T_amb). Virtual origin at ground. Calm air is an
    upper bound: crosswind bends the plume over and dilutes it faster.
    """
    rho, cp = 101_325.0 / (287.05 * T_amb), 1005.0
    B = G * conv_frac * intensity_kw_m * 1e3 / (rho * cp * T_amb)
    gprime_z = (B / (2 * alpha_entr)) ** (2 / 3)
    z = np.maximum(np.asarray(z, dtype=float), 1e-3)
    return T_amb * gprime_z / (G * z)


def line_plume_w(intensity_kw_m, T_amb=288.0, alpha_entr=0.16, conv_frac=0.75):
    """Height-independent vertical velocity (m/s) of the same line plume."""
    rho, cp = 101_325.0 / (287.05 * T_amb), 1005.0
    B = G * conv_frac * intensity_kw_m * 1e3 / (rho * cp * T_amb)
    return (B / (2 * alpha_entr)) ** (1 / 3)


def byram_flame_length(intensity_kw_m):
    """Byram (1959) flame length (m) for surface fires, I in kW/m."""
    return 0.0775 * np.asarray(intensity_kw_m) ** 0.46


def thomas_flame_length(intensity_kw_m):
    """Thomas (1963) flame length (m) above the fuel, often used for crown fires, I in kW/m."""
    return 0.0266 * np.asarray(intensity_kw_m) ** (2 / 3)


class FireColumn:
    """Vertical profile of temperature, electron density and refractivity above a fireline.

    Zones: flame band 0 <= z <= H_flame (mean temperature T_flame, electron density
    ne_flame, measured anchors), then a line plume above it. Plume electron density is
    given by one of two models:
      'saha'   local thermal equilibrium (Saha for K, attachment equilibrium for O2-),
               potassium diluted with the plume (conserved scalar ~ excess temperature)
      'frozen' optimistic bound: ions diluted but not recombined, electrons only lost
               to attachment equilibrium
    """

    def __init__(self, intensity_kw_m, H_flame, T_flame, ne_flame, nu_flame,
                 T_amb=288.0, rh=0.25, p_hpa=1000.0, alpha_entr=0.16, conv_frac=0.75,
                 water_per_heat=0.7 / 15e6, plume_ne_model="saha", x_K=1e-5):
        self.I, self.H, self.Tf = intensity_kw_m, H_flame, T_flame
        self.ne_f, self.nu_f, self.Ta = ne_flame, nu_flame, T_amb
        self.rh, self.p = rh, p_hpa
        self.alpha, self.conv = alpha_entr, conv_frac
        self.wph = water_per_heat  # kg water vapour released per J of convective heat
        self.model = plume_ne_model
        # Thermal ionization of K at the mean flame temperature (~1100 K) gives far fewer
        # electrons than measured, because ionization happens in hotter reaction zones.
        # We therefore define an effective ionization temperature T_ion that makes Saha
        # equilibrium with an assumed K mole fraction x_K reproduce the measured ne_flame.
        self.xK = x_K
        self.nK_flame = x_K * p_hpa * 100 / (K_B * T_flame)
        target = ne_flame / free_electron_fraction(T_flame)
        self.T_ion = brentq(lambda T: saha_ne(T, self.nK_flame) - target, 600.0, 5000.0)

    def dT(self, z):
        z = np.asarray(z, dtype=float)
        dTf = self.Tf - self.Ta
        plume = line_plume_dT(z, self.I, self.Ta, self.alpha, self.conv)
        return np.where(z <= self.H, dTf, np.minimum(dTf, plume))

    def T(self, z):
        return self.Ta + self.dT(z)

    def ne(self, z):
        z = np.asarray(z, dtype=float)
        T = self.T(z)
        dil = self.dT(z) / (self.Tf - self.Ta)          # conserved-scalar dilution, 1 in flame
        if self.model == "saha":
            # K diluted by entrainment; effective ionization temperature cools with the plume.
            nK = self.xK * self.p * 100 / (K_B * T) * dil
            T_ion = self.Ta + (self.T_ion - self.Ta) * dil
            ne = saha_ne(T_ion, nK) * free_electron_fraction(T)
        elif self.model == "frozen":
            ne = (self.ne_f / free_electron_fraction(self.Tf)) * dil * free_electron_fraction(T)
        else:
            raise ValueError(self.model)
        return np.where(z <= self.H, self.ne_f, np.minimum(ne, self.ne_f))

    def nu(self, z):
        return collision_freq(self.T(z), self.nu_f, self.Tf)

    def vapour_hpa(self, z):
        """Ambient vapour pressure plus combustion water mixed in proportion to excess heat."""
        T = self.T(z)
        es_amb = 6.1121 * np.exp(17.502 * (self.Ta - 273.15) / (self.Ta - 32.18))
        e_amb = self.rh * es_amb
        rho = self.p * 100 / (287.05 * T)
        rho_v = self.wph * rho * 1005.0 * self.dT(z)     # kg/m^3 of combustion water
        return e_amb + rho_v * 461.5 * T / 100.0

    def N_thermal(self, z):
        """Radio refractivity (N-units) from ITU-R P.453 using local T, P and vapour pressure."""
        T, e = self.T(z), self.vapour_hpa(z)
        return 77.6 / T * (self.p + 4810.0 * e / T)

    def N_ambient(self):
        es = 6.1121 * np.exp(17.502 * (self.Ta - 273.15) / (self.Ta - 32.18))
        return 77.6 / self.Ta * (self.p + 4810.0 * self.rh * es / self.Ta)

    def delta_n(self, z, f_hz):
        """Complex excess refractive index relative to ambient air (thermal + plasma)."""
        dn_th = (self.N_thermal(z) - self.N_ambient()) * 1e-6
        dn_pl = drude_index(f_hz, self.ne(z), self.nu(z)) - 1.0
        return dn_th + dn_pl


# ---------------------------------------------------------------------------
# 3. Diffraction through a horizontally stratified screen (1-D Fresnel-Kirchhoff)
# ---------------------------------------------------------------------------
def fresnel_radius(f_hz, d1, d2):
    lam = C0 / f_hz
    return np.sqrt(lam * d1 * d2 / (d1 + d2))


def screen_field(z_edges, t_vals, f_hz, d1, d2):
    """Normalized field E/E0 behind a thin screen whose complex transmission t depends only
    on height z relative to the direct ray (z < 0 below the ray).

    The screen extends uniformly in the horizontal transverse direction (a long fireline),
    so the transverse integral is the free-space one. t is piecewise constant on the
    intervals [z_edges[i], z_edges[i+1]] and equals 1 outside them, except that
    t_below applies from -inf to z_edges[0] (pass t_vals with one extra leading value).
    Exact for piecewise-constant t (uses Fresnel integrals).
    """
    lam = C0 / f_hz
    deff = d1 * d2 / (d1 + d2)
    v = np.asarray(z_edges) * np.sqrt(2 / (lam * deff))
    S, Cc = fresnel(v)
    F = Cc - 1j * S                                   # integral of exp(-i pi v^2/2) from 0 to v
    t_below, t_seg = t_vals[0], np.asarray(t_vals[1:])
    pieces = (F[1:] - F[:-1]) * t_seg
    lower = (F[0] - (-0.5 + 0.5j)) * t_below          # from -inf to v0, F(-inf) = -(0.5 - 0.5i)
    upper = (0.5 - 0.5j) - F[-1]                      # from v_last to +inf with t = 1
    return 0.5 * (1 + 1j) * (lower + pieces.sum() + upper)


def column_loss_db(col: FireColumn, f_hz, d1, d2, clearance, path_flame, path_plume=None,
                   dz=None, z_top=None):
    """Mean excess loss (dB) for a link whose ray passes `clearance` metres above ground at a
    point d1 from the transmitter and d2 from the receiver, over a burning fireline.

    path_flame: beam path length through the flaming zone (m), path_plume: through the plume
    (defaults to flame path plus plume spreading 2 alpha z). Ground is an opaque half-plane.
    Returns (loss_db_with_fire, loss_db_ground_only).
    """
    rF = fresnel_radius(f_hz, d1, d2)
    k0 = 2 * np.pi * f_hz / C0
    dz = dz or min(0.05 * rF, max(col.H / 20, 0.05))
    z_top = z_top or max(clearance + 4 * rF, col.H * 3)
    zg = np.arange(0.0, z_top + dz, dz)               # heights above ground, cell edges
    zc = 0.5 * (zg[1:] + zg[:-1])
    if path_plume is None:
        path = np.where(zc <= col.H, path_flame, path_flame + 2 * col.alpha * zc)
    else:
        path = np.where(zc <= col.H, path_flame, path_plume)
    t = np.exp(1j * k0 * col.delta_n(zc, f_hz) * path)
    edges = zg - clearance                            # relative to the ray
    E_fire = screen_field(edges, np.concatenate([[0.0], t]), f_hz, d1, d2)
    E_gnd = screen_field(edges[:1], np.array([0.0]), f_hz, d1, d2)
    return -20 * np.log10(abs(E_fire)), -20 * np.log10(abs(E_gnd))


# ---------------------------------------------------------------------------
# 4. Scintillation from plume turbulence (weak-fluctuation Rytov theory)
# ---------------------------------------------------------------------------
def plume_cn2(col: FireColumn, z, sigma_ratio=0.4, L0=None):
    """Refractive index structure parameter (m^-2/3) in the plume at height z.

    Temperature fluctuation sigma_T = sigma_ratio * mean excess temperature (centreline
    intensity ~0.4 in buoyant plumes); outer scale L0 ~ plume half-width alpha z.
    C_T^2 = 2 sigma_T^2 L0^(-2/3); C_n = |dn/dT| C_T including the water term.
    """
    z = np.asarray(z, dtype=float)
    dT = col.dT(z)
    sT = sigma_ratio * dT
    L0 = L0 if L0 is not None else np.maximum(col.alpha * z, 0.5)
    CT2 = 2 * sT**2 * L0 ** (-2 / 3)
    dNdT = (col.N_thermal(z) - col.N_ambient()) / np.maximum(dT, 1e-6)  # secant slope
    return (dNdT * 1e-6) ** 2 * CT2


def rytov_logamp_std_db(f_hz, d1, d2, cn2, thickness):
    """Std of received level (dB) for a thin turbulent slab at d1 (spherical wave, Rytov).

    sigma_chi^2 = 0.563 k^(7/6) Cn^2 dx (d1 d2 / L)^(5/6); level std in dB = 8.686 sigma_chi.
    """
    k = 2 * np.pi * f_hz / C0
    L = d1 + d2
    s2 = 0.563 * k ** (7 / 6) * cn2 * thickness * (d1 * d2 / L) ** (5 / 6)
    return NP_TO_DB * np.sqrt(s2), s2
