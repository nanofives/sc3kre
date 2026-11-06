#pragma once
#include <algorithm>
#include <cmath>

namespace flight {
struct Vec { double x=0,z=0; };
inline Vec operator+(Vec a,Vec b){return {a.x+b.x,a.z+b.z};}
inline Vec operator-(Vec a,Vec b){return {a.x-b.x,a.z-b.z};}
inline Vec operator*(Vec a,double s){return {a.x*s,a.z*s};}
inline double length(Vec a){return std::hypot(a.x,a.z);}
inline Vec limited(Vec a,double cap){double n=length(a);return n>cap&&n>0?a*(cap/n):a;}
struct Body { Vec position,velocity; };
inline Vec arrival(Vec position,Vec target,double cruise){
    Vec delta=target-position;
    const double d=length(delta);
    if(d<.025)return {};
    // Ease to a hover without an instant position correction.
    return delta*(std::min(cruise,d*1.25)/d);
}
inline void advance(Body& b,Vec desired,double dt,double cruise,double acceleration){
    dt=std::clamp(dt,0.,.08);
    desired=limited(desired,cruise);
    b.velocity=b.velocity+limited(desired-b.velocity,acceleration*dt);
    b.velocity=limited(b.velocity,cruise);
    b.position=b.position+b.velocity*dt;
}
inline double turnToward(double angle,double target,double dt){
    constexpr double pi=3.141592653589793;
    double delta=std::remainder(target-angle,2*pi);
    return angle+std::clamp(delta,-.65*dt,.65*dt);
}
inline double turnYaw(double angle,double target,double dt){
    constexpr double pi=3.141592653589793;
    return angle+std::clamp(std::remainder(target-angle,2*pi),-1.5*dt,1.5*dt);
}
// Artwork order: W,NW,N,NE,E,SE,S,SW. Isometric vertical projection is half scale.
inline int screenHeading(double yaw,Vec right,Vec up){
    const Vec nose{std::cos(yaw),std::sin(yaw)};
    const double sx=nose.x*right.x+nose.z*right.z;
    const double sy=(nose.x*up.x+nose.z*up.z)*.5;
    const double angle=std::atan2(sy,sx);
    return (int(std::lround((3.141592653589793-angle)/.7853981633974483))+8)%8;
}

}
