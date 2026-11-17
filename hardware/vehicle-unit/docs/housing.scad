// WildfireGuardian vehicle unit: parametric roof-box concept (OpenSCAD 2021.01 or later).
//
// CONCEPT ONLY. Not fabricated, not fitted to real boards, not tested (status 2026-11-17).
// Units: millimetres. Vehicle axes: X forward, Y to the vehicle's left, Z up.
// Origin: centre of the footprint on the roof skin (Z = 0 under the magnets).
//
// The top-level numeric parameters below mirror HOUSING in docs/make_drawings.py (same names);
// docs/test_docs.py fails if they drift apart. Change both together, then re-run make_drawings.py.
//
// Radome: transparent at normal incidence when t = n * lambda0 / (2 * sqrt(eps_r)), lambda0 = c / f.
//   f = 60 GHz -> lambda0 = 4.997 mm. PC eps_r ~ 2.9 -> 1.47 mm per half wave; PTFE eps_r ~ 2.1 -> 1.72 mm.
//   eps_r values are typical handbook values: measure the actual sheet, or tune with test B (corner reflector).
//
// Render parts: set `part` to "assembly", "enclosure", "radome", "base", "shield", "plate_bracket".

part = "assembly";

// ---- parameters (mirrored in make_drawings.py HOUSING) ----
box_l = 160;          // enclosure length along X, external
box_w = 220;          // enclosure width along Y, external
box_h = 90;           // enclosure height along Z, external
wall = 3;             // die-cast aluminium wall
base_l = 240;         // base plate along X
base_w = 320;         // base plate along Y
base_t = 5;           // base plate thickness
magnet_d = 88;        // rubber-coated pot magnet diameter
magnet_h = 15;        // magnet height incl. rubber boot
radome_w = 60;        // radar window width (Y)
radome_h = 60;        // radar window height (Z)
radome_y = -45;       // window centre Y (negative = vehicle right)
radome_z = 45;        // window centre above enclosure bottom
radome_eps_r = 2.1;   // PTFE; polycarbonate ~ 2.9
radome_n = 2;         // number of half wavelengths in the slab
ir_win_d = 25;        // germanium LWIR window diameter
ir_win_t = 2;         // germanium window thickness
ir_win_y = 35;        // LWIR window centre Y
ir_win_z = 55;        // LWIR window centre above enclosure bottom
plate_a = 50;         // copper flux plate edge
plate_t = 1;          // copper flux plate thickness
board_a = 70;         // ceramic fibre board edge
board_t = 25;         // ceramic fibre board thickness
plate_proud = 40;     // plate front face ahead of enclosure front face
plate_y = 155;        // plate centre Y (outboard, vehicle left)
plate_z = 50;         // plate centre above enclosure bottom
shield_gap = 20;      // air gap lid -> sun/heat shield
shield_t = 1;         // shield sheet thickness
shield_over = 20;     // shield overhang on every side
gland_d = 16;         // M16 cable glands, rear face
rf_win_w = 80;        // rear polycarbonate RF (Wi-Fi) window width
rf_win_h = 30;        // rear RF window height

// ---- derived ----
c0 = 299792458;                                   // m/s
f_radar = 60e9;                                   // Hz, low end of the IWR6843 60-64 GHz band
lambda0_mm = c0 / f_radar * 1000;                 // 4.997 mm
radome_t = radome_n * lambda0_mm / (2 * sqrt(radome_eps_r));
echo(str("radome thickness (mm) = ", radome_t, "  [n=", radome_n, ", eps_r=", radome_eps_r, "]"));
echo(str("PC  n=1: ", lambda0_mm / (2 * sqrt(2.9)), " mm;  PTFE n=1: ", lambda0_mm / (2 * sqrt(2.1)), " mm"));

z_box0 = magnet_h + base_t;
z_box1 = z_box0 + box_h;
x_front = box_l / 2;
lid_t = wall;
gland_y = [-75, -25, 25, 75];
gland_z = 25;
vent_y = 95;
rf_win_y = -50;
rf_win_z = 65;
$fn = 48;

// ---- modules ----
module rounded_box(l, w, h, r = 4) {
    hull() for (sx = [-1, 1], sy = [-1, 1])
        translate([sx * (l / 2 - r), sy * (w / 2 - r), 0]) cylinder(r = r, h = h);
}

module enclosure() {
    // Die-cast aluminium body with front radar window, front LWIR window bore, rear glands, vent, RF window.
    color("Gainsboro") difference() {
        translate([0, 0, z_box0]) rounded_box(box_l, box_w, box_h);
        translate([0, 0, z_box0 + wall]) rounded_box(box_l - 2 * wall, box_w - 2 * wall, box_h);  // open top
        // radar window (radome sits in a 2 mm rebate from inside)
        translate([x_front - wall - 1, radome_y - radome_w / 2, z_box0 + radome_z - radome_h / 2])
            cube([wall + 2, radome_w, radome_h]);
        // LWIR window bore
        translate([x_front - wall - 1, ir_win_y, z_box0 + ir_win_z]) rotate([0, 90, 0])
            cylinder(d = ir_win_d - 4, h = wall + 2);
        // rear glands, vent, RF window
        for (gy = gland_y) translate([-x_front - 1, gy, z_box0 + gland_z]) rotate([0, 90, 0])
            cylinder(d = gland_d, h = wall + 2);
        translate([-x_front - 1, vent_y, z_box0 + gland_z]) rotate([0, 90, 0]) cylinder(d = 12, h = wall + 2);
        translate([-x_front - 1, rf_win_y - rf_win_w / 2, z_box0 + rf_win_z - rf_win_h / 2])
            cube([wall + 2, rf_win_w, rf_win_h]);
    }
    // lid (separate part in reality, gasketed)
    color("Silver") translate([0, 0, z_box1 - lid_t]) rounded_box(box_l, box_w, lid_t);
}

module radome() {
    // PTFE (or PC) slab behind the front window, overlapping the opening by 5 mm on every side.
    color("Beige", 0.8) translate([x_front - wall - radome_t, radome_y - radome_w / 2 - 5,
                                   z_box0 + radome_z - radome_h / 2 - 5])
        cube([radome_t, radome_w + 10, radome_h + 10]);
}

module ir_window() {
    // Germanium window, AR coated 8-14 um, clamped from inside with an O-ring.
    color("SlateGray") translate([x_front - wall - ir_win_t, ir_win_y, z_box0 + ir_win_z]) rotate([0, 90, 0])
        cylinder(d = ir_win_d, h = ir_win_t);
}

module rf_window() {
    color("LightBlue", 0.6) translate([-x_front + wall, rf_win_y - rf_win_w / 2 - 5, z_box0 + rf_win_z - rf_win_h / 2 - 5])
        cube([2, rf_win_w + 10, rf_win_h + 10]);
}

module base_plate() {
    color("LightSteelBlue") translate([0, 0, magnet_h]) rounded_box(base_l, base_w, base_t, 8);
}

module magnets() {
    for (sx = [-1, 1], sy = [-1, 1])
        color("DimGray") translate([sx * (base_l / 2 - 50), sy * (base_w / 2 - 60), 0])
            cylinder(d = magnet_d, h = magnet_h);
}

module shield() {
    // 1 mm aluminium sun/heat shield on four 20 mm standoffs; white-painted top.
    z0 = z_box1 + shield_gap;
    color("WhiteSmoke") translate([0, 0, z0]) rounded_box(box_l + 2 * shield_over, box_w + 2 * shield_over, shield_t, 6);
    for (sx = [-1, 1], sy = [-1, 1])
        color("Gray") translate([sx * (box_l / 2 - 20), sy * (box_w / 2 - 20), z_box1]) cylinder(d = 8, h = shield_gap);
}

module plate_bracket() {
    // Copper flux plate on ceramic fibre board, held outboard and proud of the front face.
    // The board is the insulated backing that makes the thin-skin (lumped) plate model reasonable.
    // Ceramic (not metal) spacers keep the plate electrically isolated from the chassis.
    xp = x_front + plate_proud;                  // plate front face
    zc = z_box0 + plate_z;
    color("Black") translate([xp - plate_t, plate_y - plate_a / 2, zc - plate_a / 2]) cube([plate_t, plate_a, plate_a]);
    color("Wheat") translate([xp - plate_t - board_t, plate_y - board_a / 2, zc - board_a / 2])
        cube([board_t, board_a, board_a]);
    // L-bracket from the left side wall
    color("Silver") {
        translate([xp - plate_t - board_t - 3, box_w / 2, zc - 10]) cube([3, plate_y - board_a / 2 - box_w / 2 + 10, 20]);
        // arm along the side wall, bolted to the wall over its rear 40 mm (through ceramic washers)
        translate([x_front - 40, box_w / 2, zc - 10]) cube([xp - plate_t - board_t - (x_front - 40), 3, 20]);
    }
}

module assembly() {
    magnets();
    base_plate();
    enclosure();
    radome();
    ir_window();
    rf_window();
    shield();
    plate_bracket();
}

if (part == "assembly") assembly();
else if (part == "enclosure") enclosure();
else if (part == "radome") radome();
else if (part == "base") { base_plate(); magnets(); }
else if (part == "shield") shield();
else if (part == "plate_bracket") plate_bracket();
