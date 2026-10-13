#version 300 es
precision highp float;
in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;
// Podbija ciemne tony (gamma 0.5). Czarne (0,0,0) zostaje czarne: pow(0)=0.
void main() {
    vec4 c = texture(tex, v_texcoord);
    vec3 g = pow(c.rgb, vec3(0.5));
    fragColor = vec4(mix(c.rgb, g, 0.85), c.a);
}
