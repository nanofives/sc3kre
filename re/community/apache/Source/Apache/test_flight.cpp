#include "FlightMotion.h"
#include <cassert>
#include <iostream>
using namespace flight;
int main(){
    for(double dt:{1./20,1./30,1./60}){
        Body b;
        for(int i=0;i<500;++i){
            Vec before=b.position,oldVelocity=b.velocity;
            Vec wanted=i<200?Vec{1.45,0}:i<350?Vec{-1.45,0}:Vec{};
            advance(b,wanted,dt,1.45,1.1);
            assert(length(b.velocity)<=1.450001);
            assert(length(b.position-before)<=1.450001*dt);
            assert(length(b.velocity-oldVelocity)<=1.100001*dt);
        }
        assert(length(b.velocity)<.00001);
    }
    Body follower{{-5,3},{0,0}};
    for(int i=0;i<500;++i){
        Vec target=i<200?Vec{4,3}:Vec{-4,-3};
        Vec before=follower.position;
        advance(follower,arrival(follower.position,target,1.75),1./30,1.75,1.25);
        assert(length(follower.position-before)<=1.750001/30);
    }
    assert(length(follower.position-Vec{-4,-3})<.08);
    auto run=[](double dt){Body b;for(int i=0;i<int(10./dt);++i)advance(b,{1.15,0},dt,1.15,1.1);return b.position.x;};
    assert(std::abs(run(1./20)-run(1./60))<.04);
    assert(std::abs(turnToward(3.1,-3.1,.03)-3.1)<=.650001*.03);
    Body stalled;advance(stalled,{1,0},2.,1.45,1.1);
    assert(length(stalled.position)<.01); // stall cannot cause a teleport
    // Camera-relative heading selection must cover all eight nose directions.
    const Vec right[4]={{-1,1},{1,1},{1,-1},{-1,-1}};
    const Vec up[4]={{-1,-1},{-1,1},{1,1},{1,-1}};
    for(int camera=0;camera<4;++camera){
        for(int heading=0;heading<8;++heading){
            double angle=3.141592653589793-heading*.7853981633974483;
            Vec world=right[camera]*std::cos(angle)+up[camera]*(2*std::sin(angle));
            assert(screenHeading(std::atan2(world.z,world.x),right[camera],up[camera])==heading);
        }
    }
    double yaw=0;
    for(int i=0;i<200;++i){double before=yaw;yaw=turnYaw(yaw,3.141592653589793,.02);assert(std::abs(yaw-before)<=.030001);}
    assert(std::abs(yaw-3.141592653589793)<.00001);
    std::cout<<"PASS: eight headings at all camera rotations; gradual 180-degree yaw\n";
    std::cout<<"PASS: speed, acceleration, reversing, braking, formation catch-up, frame rates, turn limit, timer stall\n";
}
