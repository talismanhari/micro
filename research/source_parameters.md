# Source Antenna Parameters & Literature Reference

## 1. Primary Research Reference
- **Title:** ULTRA HIGH BAND IMPROVEMENT OF PATCH ANTENNA
- **Authors:** J. R. Arunkumar, R. Anusuya, M. Sundarrajan, M. Ramkumar Prabhu
- **Journal:** *Journal of Engineering Sciences*, Vol. 11, Issue 2, pp. 15–19, February 2020.
- **ISSN:** 0377-9254
- **Architecture:** Coplanar Waveguide (CPW)-fed Planar Monopole Antenna

---

## 2. Dimensional & Material Specifications

All dimensions are specified in millimeters ($mm$) unless stated otherwise.

| Parameter Name | Symbol | Value | Unit | Engineering Description |
|---|---|---:|:---:|---|
| Substrate Length | $L_{sub}$ | 38.0 | mm | Total length along Y-axis |
| Substrate Width | $W_{sub}$ | 43.0 | mm | Total width along X-axis |
| Substrate Thickness | $h$ | 1.53 | mm | Dielectric substrate thickness (Z-axis) |
| Substrate Dielectric | FR4 | - | - | Standard flame retardant glass-epoxy |
| Relative Permittivity | $\epsilon_r$ | 4.4 | - | Dielectric constant at microwave frequencies |
| Loss Tangent | $\tan \delta$ | 0.02 | - | Dielectric loss dissipation factor |
| Copper Thickness | $t$ | 0.1 | mm | Metallization sheet thickness |
| Square Patch Length | $L_p$ | 18.4 | mm | Radiating element length |
| Square Patch Width | $W_p$ | 18.4 | mm | Radiating element width |
| Ground Plane Length | $L_g$ | 18.4 | mm | CPW symmetrical ground plane length |
| Ground Plane Width | $W_g$ | 16.9 | mm | Symmetrical CPW ground plane width (each side) |
| Feed Line Width | $W_f$ | 3.1 | mm | 50 $\Omega$ CPW central conductor strip width |
| Feed-to-Ground Gap | $g_f$ | 0.55 | mm | Symmetrical lateral CPW spacing |
| Patch-to-Ground Gap | $g_p$ | 0.50 | mm | Axial spacing between ground top and patch bottom |

---

## 3. Coordinate System & Structural Reconstruction

The antenna is built in the Cartesian coordinate system:
- **Z-axis:** Substrate spans $z \in [-1.53, 0.0]\text{ mm}$. All metallization (patch, feed line, coplanar grounds) is deposited on the top surface ($z = 0.0\text{ mm}$) with thickness $t = 0.1\text{ mm}$ (or modeled as 2D Perfect E / Copper finite conductivity boundary).
- **X-axis (Width, 43.0 mm total):** Centered at $x = 0$:
  - Substrate spans $x \in [-21.5, +21.5]\text{ mm}$.
  - Central CPW feed line: $x \in [-1.55, +1.55]\text{ mm}$ ($W_f = 3.1\text{ mm}$).
  - Feed-to-ground gaps: $x \in [-2.10, -1.55]\text{ mm}$ and $x \in [+1.55, +2.10]\text{ mm}$ ($g_f = 0.55\text{ mm}$).
  - Left ground plane: $x \in [-19.0, -2.10]\text{ mm}$ ($W_g = 16.9\text{ mm}$).
  - Right ground plane: $x \in [+2.10, +19.0]\text{ mm}$ ($W_g = 16.9\text{ mm}$).
  - Outer substrate lateral margins: $2.5\text{ mm}$ on each side ($[-21.5, -19.0]$ and $[+19.0, +21.5]\text{ mm}$).
- **Y-axis (Length, 38.0 mm total):**
  - Substrate spans $y \in [0.0, 38.0]\text{ mm}$.
  - CPW grounds and feed line input start at port edge $y = 0.0\text{ mm}$.
  - Ground planes terminate at $y = 18.4\text{ mm}$ ($L_g = 18.4\text{ mm}$).
  - Central feed line extends from $y = 0.0\text{ mm}$ to $y = 18.9\text{ mm}$ ($L_g + g_p = 18.4 + 0.5\text{ mm}$), directly contacting the radiating patch.
  - Radiating patch spans $y \in [18.9, 37.3]\text{ mm}$ ($L_p = 18.4\text{ mm}$) and $x \in [-9.2, +9.2]\text{ mm}$ ($W_p = 18.4\text{ mm}$).
  - Top dielectric margin: $y \in [37.3, 38.0]\text{ mm}$ ($0.7\text{ mm}$ margin).

---

## 4. Geometric Ambiguities & Documented Assumptions

1. **Corner Truncation Placement:**
   - In planar monopole theory, truncating the lower corners adjacent to the ground plane provides a smooth impedance transition, expanding bandwidth.
   - For Type B and Type C, the default implementation cuts the **bottom two corners** facing the CPW ground planes ($(x = -9.2, y = 18.9)$ and $(x = +9.2, y = 18.9)$).
   - The configuration system includes a parameter `truncation_corners: "bottom"` (with configurable option `"all"` for research comparison) so that this assumption remains explicit and customizable.

2. **Circular Truncation Geometry (Type C):**
   - The paper specifies cutting radius `RAD` $\in \{13.0, 12.0, 11.0, 10.0, 10.2\}\text{ mm}$.
   - In circular truncation of a corner, a circle or fillet of radius $R$ intersects the adjacent edges at distance $R$ from the corner vertex. When $R > W_p / 2 = 9.2\text{ mm}$, the circular cut center must be carefully positioned outside the patch boundary such that the circular arc smoothly sculpts the corner transition.
   - Default assumption: The cutting circle of radius $R$ is centered at $(x_c, y_c) = (\pm(W_p/2 - \Delta_x), y_{bottom} + \Delta_y)$ or parameterized fillet cut. Both exact subtractive circular cylinders and tangent arc fillets are supported.
