#include <cmath>
#include <limits>
#include <vector>
// Minimize a scalar exposure estimate for each (road state, time), storing a
// predecessor. All published paths require the caller's authoritative recheck.
extern "C" int findwalk(int n,int m,int dep,int last,int s,int z,int dwell,int bins,int step,
 const int* target,const int* moving,const int* head,const int* dest,const int* duration,const int* geo,const int* lower,const int* goal,
 const float* rates,const double* prefixes,const int* starts,const int* low,const int* high,
 double budget,int dwell_geo,int* out,int* arrival,double* dose) {
 const long count=long(n)*(last-dep+1);if(count>50000000)return -1;
 std::vector<double> costs(count,std::numeric_limits<double>::infinity());
 std::vector<int> pred(count,-1),from(m);
 for(int u=0;u<n;u++)for(int e=head[u];e<head[u+1];e++)from[e]=u;
 auto val=[&](int i,int t){auto ix=long(i)*bins+t/step;return prefixes[ix]+rates[ix]*(t%step);};
 auto permits=[&](int i,int t){for(int b=starts[i];b<starts[i+1];b++)if(low[b]<=t&&t<high[b])return false;return true;};
 costs[s]=0;
 for(int t=dep;t<=last;t++){
  long off=long(t-dep)*n;
  for(int u=0;u<n;u++){
   double c=costs[off+u];if(!std::isfinite(c)||t+lower[u]>last)continue;
   for(int e=head[u];e<head[u+1];e++){
    int v=dest[e],g=geo[e],nt=t+duration[e];if(nt+lower[v]>last||!permits(g,t))continue;
    double vcost=c+val(g,nt)-val(g,t);
    // Fresh physical arrival; holds at destination never make a new arrival.
    if(target[v] && goal[nt] && moving[g] && permits(dwell_geo,nt)){
     double complete=vcost+val(dwell_geo,nt+dwell)-val(dwell_geo,nt);
     if(complete<=budget && (*arrival<0||nt<*arrival||(nt==*arrival&&complete<*dose))){
       *arrival=nt;*dose=complete;int k=0;out[k++]=g;int at=u,clock=t;
       while(clock>dep){
        int pe=pred[long(clock-dep)*n+at];if(pe<0)return -2;
        out[k++]=geo[pe];at=from[pe];clock-=duration[pe];
       }
       out[k]=-1;
     }
    }
    if(vcost>budget||(*arrival>=0&&nt>=*arrival))continue;
    long ix=long(nt-dep)*n+v;if(costs[ix]>vcost){costs[ix]=vcost;pred[ix]=e;}
   }
  }
  if(*arrival>=0&&t>=*arrival)break;
 }
 return 0;
}
