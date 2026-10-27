shader_type spatial;
render_mode diffuse_burley;
uniform sampler2D weights0 : filter_linear, repeat_disable;
uniform sampler2D weights1 : filter_linear, repeat_disable;
uniform sampler2D dust_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dust_normal : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dunes_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dunes_normal : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D bedrock_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D bedrock_normal : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rubble_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rubble_normal : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D strata_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D strata_normal : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D sediment_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D sediment_normal : filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool stone_surface=false;
uniform bool local_surface=false;
varying vec3 terrain_world;
varying vec3 terrain_normal;
varying vec3 surface_position;
varying vec3 surface_normal;
varying vec3 surface_x;
varying vec3 surface_z;
void vertex(){
 terrain_world=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;terrain_normal=normalize(mat3(MODEL_MATRIX)*NORMAL);
 surface_position=VERTEX;surface_normal=NORMAL;
 surface_x=normalize(mat3(MODEL_MATRIX)*vec3(1.0,0.0,0.0));
 surface_z=normalize(mat3(MODEL_MATRIX)*vec3(0.0,0.0,1.0));
}
void layer(sampler2D color_map,sampler2D normal_map_tex,vec2 uv,float weight,inout vec4 colors,inout vec4 normals){
 if(weight>.015){vec4 color=texture(color_map,uv);float contribution=weight*mix(.6,1.4,color.a);colors+=vec4(color.rgb,1.0)*contribution;normals+=texture(normal_map_tex,uv)*contribution;}
}
void fragment(){
 vec3 base_normal=normalize(terrain_normal);vec3 facing=abs(base_normal);
 vec3 a;vec3 b;
 if(local_surface){a=vec3(.64,0.0,.24);b=vec3(.12,0.0,0.0);}
 else{
  vec2 control_uv=(terrain_world.xz+vec2(256.5))/512.0;
  a=texture(weights0,control_uv).rgb;b=texture(weights1,control_uv).rgb;
  float wet=1.0-smoothstep(-1.0,.5,terrain_world.y);b.b*=wet;
  float cliff=smoothstep(.25,.65,1.0-facing.y);
  a=mix(a,vec3(.015,0.0,.4),cliff);b=mix(b,vec3(.06,.9,0.0),cliff);
 }
 a.r+=.008;
 if(stone_surface){a=vec3(0.0,0.0,.72);b=vec3(.04,.24,0.0);}
 float sum=max(dot(a,vec3(1.0))+dot(b,vec3(1.0)),.001);a/=sum;b/=sum;
 vec3 projected_position=local_surface?surface_position:terrain_world;
 vec3 projected_facing=local_surface?abs(normalize(surface_normal)):facing;
 vec2 projection=projected_facing.y>=max(projected_facing.x,projected_facing.z)?projected_position.xz:(projected_facing.x>projected_facing.z?projected_position.zy:projected_position.xy);
 vec2 uv=projection*.25;vec4 colors=vec4(0.0);vec4 normals=vec4(0.0);
 layer(dust_albedo,dust_normal,uv,a.r,colors,normals);
 layer(dunes_albedo,dunes_normal,uv,a.g,colors,normals);
 layer(bedrock_albedo,bedrock_normal,uv,a.b,colors,normals);
 layer(rubble_albedo,rubble_normal,uv,b.r,colors,normals);
 layer(strata_albedo,strata_normal,uv,b.g,colors,normals);
 layer(sediment_albedo,sediment_normal,uv,b.b,colors,normals);
 float total=max(colors.a,.001);vec3 relief=normalize(normals.rgb/total*2.0-1.0);
 bool use_z=projected_facing.x>projected_facing.z && projected_facing.y<projected_facing.x;
 vec3 axis=local_surface?(use_z?surface_z:surface_x):(use_z?vec3(0.0,0.0,1.0):vec3(1.0,0.0,0.0));
 vec3 tangent=normalize(axis-base_normal*dot(axis,base_normal));vec3 bitangent=normalize(cross(base_normal,tangent));
 vec3 normal_world=normalize(base_normal*relief.z+tangent*relief.x*.55+bitangent*relief.y*.55);
 NORMAL=normalize((VIEW_MATRIX*vec4(normal_world,0.0)).xyz);
 ALBEDO=colors.rgb/total;ROUGHNESS=clamp(normals.a/total,.65,1.0);METALLIC=0.0;SPECULAR=0.0;
}
