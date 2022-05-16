#include <cstdint>
#include <cstddef>
#include <map>
#include <unordered_map>
#include <string>
#include <vector>
#include <list>
#include <iostream>
#include <array>


struct node
{
	node* left = nullptr;
	node* right = nullptr;
	uint64_t value = 42;
};

struct tree
{
	size_t sz = 0;
	node* n = nullptr;
};

union nunion
{
	uint32_t u;
	float f;
};

struct xtree
{
	std::string str{"HELLO WORLD STRING"};
	std::string& xstr = str;
	std::unordered_map<int,int> u;
	std::vector<int> v { 1,2,3,4,5,6,7,8 };
	std::vector<std::string> sv { "1","2","3","4","5","6" };
	std::array<double,13> a;
	std::map<int,int> m;
	std::map<int,int> bl;
	std::list<std::string> l { "A","B","L" };
	void* ptr = &m;
	void* ptrptr = &ptr;
	nunion NU;
	nunion nu[2];
};

struct us
{
	union {
		uint64_t u64;
		double dx;
	};
};

struct vm2
{
	std::vector<int> v0 = { 1,2 };
	std::vector<int> v1 = { 3,4 };
};

struct vm2a
{
	std::vector<int> v[2] = { { 1,2 }, { 3,4 } };
	std::vector<long> lv[2] { { 42 }, { 43 }  };
};

struct va
{
	uint64_t value = 42;
};

struct vb : va
{
	double value = 43;
};

struct vc : vb
{
	int x = 36;
};

template<class T, class X>
void rabbit( T* t, X* x )
{
	free(t);
	free(x);
}

template<class T,class X>
void hole( T* t, X* x, int level )
{
	if( level == 0 )
	{
		rabbit(t,x);
	}
	hole(t,x,level-1);
}

int main(int argc, const char *argv[])
{
	std::cout << "argc = " << argc << "\n";
	
	us un;
	tree t;
	t.n = new node;
	t.n->left = new node;
	t.n->right = new node;

	void* vptr = t.n;



	std::map<int,int> m;
	m[42] = 58;
	m[43] = 59;
	m[44] = 60;
	m[45] = 61;

	std::unordered_map<int,int> u;
	u[42] = 58;
	u[43] = 59;
	u[44] = 60;
	u[45] = 61;

	xtree x;
	x.u = u;
	x.m = m;

	x.ptr = vptr;
	x.ptrptr = &vptr;

	vm2 v;
	vm2a va;
	va.lv[0].clear();
	va.lv[1].clear();

	vc vv;

	if( t.n->right->left )
	{

//	t.n->right->left->value = 53; // crash it
		t.n->right->left = (node*)0x42;
	}
//	rabbit(t.n->right->left,&m);
	hole(t.n->right->left,&m,7);
}
// vim: tabstop=4 shiftwidth=4 noexpandtab
