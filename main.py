from direct.showbase.ShowBase import ShowBase
from panda3d.core import PointLight, AmbientLight
from panda3d.core import Vec4
from panda3d.core import Shader
from direct.showbase.BufferViewer import BufferViewer


# Shaders adapted from examples by @wezu:
# https://discourse.panda3d.org/t/shadows-made-easy/15399
v_shader='''
#version 330
uniform struct p3d_LightSourceParameters {
    // Primary light color.
    vec4 color;

    // Light color broken up into components, for compatibility with legacy
    // shaders.  These are now deprecated.
    vec4 ambient;
    vec4 diffuse;
    vec4 specular;

    // View-space position.  If w=0, this is a directional light, with the xyz
    // being -direction.
    vec4 position;

    // Spotlight-only settings
    vec3 spotDirection;
    float spotExponent;
    float spotCutoff;
    float spotCosCutoff;

    // Individual attenuation constants
    float constantAttenuation;
    float linearAttenuation;
    float quadraticAttenuation;

    // constant, linear, quadratic attenuation in one vector
    vec3 attenuation;

    // Shadow map for this light source
    // ENABLE FOR HARD SHADOWS:
    //samplerCube shadowMap;

    // ENABLE FOR SOFT SHADOWS:
    samplerCubeShadow shadowMap;

    // Transforms view-space coordinates to shadow map coordinates
    mat4 shadowViewMatrix;
} p3d_LightSource[1];

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat3 p3d_NormalMatrix;
uniform mat4 p3d_ModelViewMatrix;

in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;

out vec2 uv;
out vec4 shadow_uv;
out vec3 normal;

out vec3 vertex_viewspace;
out vec3 normal_viewspace;

void main()
    {
    //position    
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;      
    //normal      
    normal = p3d_NormalMatrix * p3d_Normal;
    //uv
    uv = p3d_MultiTexCoord0;

    normal_viewspace = normalize( p3d_NormalMatrix * p3d_Normal );
    vertex_viewspace = vec3(p3d_ModelViewMatrix * p3d_Vertex);
    //shadows
    //shadow_uv = p3d_LightSource[0].shadowViewMatrix * p3d_Vertex;
    shadow_uv = p3d_LightSource[0].shadowViewMatrix * vec4(vertex_viewspace, 1);
    //shadow_uv = p3d_LightSource[0].shadowViewMatrix * (p3d_ModelViewMatrix * p3d_Vertex);

}
'''

#fragment shader
f_shader='''
#version 330

uniform sampler2D p3d_Texture0;
uniform vec3 camera_pos;
uniform float shadow_blur;

in vec2 uv;
in vec4 shadow_uv;
in vec3 normal;
in vec3 vertex_viewspace;
in vec3 normal_viewspace;

out vec4 out_color;


float NEAR = 1;
float FAR = 500;
in vec4 shadow_coords;

uniform struct p3d_LightSourceParameters {
    // Primary light color.
    vec4 color;

    // Light color broken up into components, for compatibility with legacy
    // shaders.  These are now deprecated.
    vec4 ambient;
    vec4 diffuse;
    vec4 specular;

    // View-space position.  If w=0, this is a directional light, with the xyz
    // being -direction.
    vec4 position;

    // Spotlight-only settings
    vec3 spotDirection;
    float spotExponent;
    float spotCutoff;
    float spotCosCutoff;

    // Individual attenuation constants
    float constantAttenuation;
    float linearAttenuation;
    float quadraticAttenuation;

    // constant, linear, quadratic attenuation in one vector
    vec3 attenuation;

    // Shadow map for this light source
    // ENABLE FOR HARD SHADOWS:
    //samplerCube shadowMap;

    // ENABLE FOR SOFT SHADOWS:
    samplerCubeShadow shadowMap;

    // Transforms view-space coordinates to shadow map coordinates
    mat4 shadowViewMatrix;
} p3d_LightSource[1];

float hardShadow(samplerCube tex, vec3 uv, float bias, float depth)
{
	float closestDepth = texture(tex, uv).r; 

	float shadow = 0.0;
	if(depth - bias < closestDepth)
		shadow += 1.0;
	return shadow;
}

float calcShadow( vec4 shadow_coords )
{
	vec4 coords;
	coords.xyz = shadow_coords.xyz / shadow_coords.w;
	float dist = max(abs(coords.x), max(abs(coords.y), abs(coords.z)));
	coords.w = (NEAR + FAR) / (FAR - NEAR) + ((-2 * FAR * NEAR) / (dist * (FAR - NEAR)));
	coords.w = coords.w * 0.5 + 0.5;

        // ENABLE FOR HARD SHADOWS:
        //float shadow = hardShadow( p3d_LightSource[0].shadowMap, coords.xyz, 1e-4, coords.w );

        // ENABLE FOR SOFT SHADOWS:
	float shadow = texture( p3d_LightSource[0].shadowMap, coords );

	return shadow;
}

void main()
{
    //base color
    vec3 ambient=vec3(0.03, 0.03, 0.03);    
    //texture        
    vec4 tex=texture(p3d_Texture0, uv);        
    //light ..sort of, not important
    vec3 light=p3d_LightSource[0].color.rgb*max(dot(normalize(normal),-p3d_LightSource[0].spotDirection), 0.0);

    vec3 diffuseCol = tex.rgb;
    float shininess = 1;

    vec3 color = vec3(0,0,0);
    vec3 diff = p3d_LightSource[0].position.xyz - vertex_viewspace * p3d_LightSource[0].position.w;
    vec3 L = normalize(diff);
    vec3 E = normalize(-vertex_viewspace);
    vec3 R = normalize(-reflect(L, normal_viewspace));
    float diffusePower = max(dot(normal_viewspace, L), 0) * 0.5;

    float specularPower = pow(diffuseCol.r*max(dot(R, E), 0), shininess);

    float len = length(diff);
    float attenuation = 1 / dot(p3d_LightSource[0].attenuation, vec3(1, len, len*len));

    float specular = 0.1;

    color += diffuseCol.rgb * p3d_LightSource[0].color.rgb * diffusePower * attenuation;
    color += p3d_LightSource[0].color.rgb * specularPower * specular * attenuation;

    // calculate shadow
    float shadow = calcShadow( shadow_uv );
    //make the shadow brighter
    shadow=0.5+shadow*0.5;

    //out_color=vec4(shadow,shadow,shadow,1);//, tex.a);
    out_color = vec4(ambient+color*shadow, tex.a);

}'''                    

class MyApp(ShowBase):

    def __init__(self):

        ShowBase.__init__(self)

        # Load the environment model.
        self.scene = self.loader.loadModel("environment.egg")

        # Reparent the model to render.
        self.scene.reparentTo(self.render)

        # Apply scale and position transforms on the model.
        self.scene.setScale(0.25, 0.25, 0.25)
        self.scene.setPos(-8, 42, 0)

        # Set up point light that will cast shadows:
        plight = PointLight('plight')
        plight.setColorTemperature( 3600 )
        plight.setShadowCaster(True, 2048, 2048)
        plnp = render.attachNewNode(plight)
        plnp.setPos(0, 0, 5)
        render.setLight(plnp)

        for i in range(6):
            plight.getLens(i).setNear(1)
            plight.getLens(i).setFar(500)

        # Let environment receive shadows:
        self.init_shaders()

        self.accept("v", base.bufferViewer.toggleEnable)

    def init_shaders(self):

        shader = Shader.make(Shader.SL_GLSL, v_shader, f_shader)
        self.scene.setShader(shader)
        self.scene.set_two_sided(True)
        #self.scene.ls()
 

app = MyApp()
app.run()
